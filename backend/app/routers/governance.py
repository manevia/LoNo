from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from ..db import db
from ..security import get_user, get_user_optional
from ..util import now, now_iso, uid

router = APIRouter(prefix="/governance", tags=["governance"])
MIN_STAKE_TO_PROPOSE = 100.0


class VoteIn(BaseModel):
    proposal_id: str
    choice: Literal["for", "against", "abstain"]


class ProposalIn(BaseModel):
    title: str = Field(min_length=8, max_length=120)
    summary: str = Field(min_length=20, max_length=2000)
    days: Literal[3, 7, 14] = 7


def _status(p) -> str:
    if p.get("status") in ("passed", "rejected"):
        return p["status"]
    if datetime.fromisoformat(p["ends_at"]) > now():
        return "active"
    v = p.get("votes", {})
    return "passed" if v.get("for", 0) > v.get("against", 0) else "rejected"


@router.get("/proposals")
async def proposals(user=Depends(get_user_optional)):
    props = await db.proposals.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    mine = {}
    if user:
        async for v in db.votes.find({"user_id": user["id"]}, {"proposal_id": 1, "choice": 1}):
            mine[v["proposal_id"]] = v["choice"]
    for p in props:
        p["status"] = _status(p)
        p["my_vote"] = mine.get(p["id"])
    return props


@router.post("/proposals")
async def create_proposal(body: ProposalIn, user=Depends(get_user)):
    u = await db.users.find_one({"id": user["id"]}, {"wallet": 1})
    if u["wallet"]["staked"] < MIN_STAKE_TO_PROPOSE:
        raise HTTPException(400, f"Stake at least {MIN_STAKE_TO_PROPOSE:.0f} $LONO to submit a proposal")
    p = {"id": uid(), "title": body.title, "summary": body.summary, "author_id": user["id"],
         "author_name": user["name"], "status": "active",
         "votes": {"for": 0, "against": 0, "abstain": 0},
         "ends_at": (now() + timedelta(days=body.days)).isoformat(), "created_at": now_iso()}
    await db.proposals.insert_one(p)
    p.pop("_id", None)
    return p


@router.post("/vote")
async def vote(body: VoteIn, user=Depends(get_user)):
    p = await db.proposals.find_one({"id": body.proposal_id})
    if not p:
        raise HTTPException(404, "Proposal not found")
    if _status(p) != "active":
        raise HTTPException(400, "Voting on this proposal has closed")
    u = await db.users.find_one({"id": user["id"]}, {"wallet": 1})
    power = round(u["wallet"]["lono_balance"] + u["wallet"]["staked"] * 2, 4)
    if power < 1:
        raise HTTPException(400, "You need at least 1 $LONO of voting power")
    if await db.votes.find_one({"proposal_id": p["id"], "user_id": user["id"]}, {"_id": 1}):
        raise HTTPException(400, "You already voted on this proposal")
    try:  # unique index also guards against a double-submit race
        await db.votes.insert_one({"id": uid(), "proposal_id": p["id"], "user_id": user["id"],
                                   "choice": body.choice, "power": power, "at": now_iso()})
    except DuplicateKeyError:
        raise HTTPException(400, "You already voted on this proposal")
    await db.proposals.update_one({"id": p["id"]}, {"$inc": {f"votes.{body.choice}": power}})
    return {"ok": True, "power": power}
