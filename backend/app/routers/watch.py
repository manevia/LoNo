"""Watch-to-Earn with server-side verification.

The client opens a session when playback starts and sends a heartbeat every
HEARTBEAT_SEC while media is playing. The server credits only wall-clock time
it observed between heartbeats (each gap capped at 1.5x the interval), so a
client can't claim minutes it didn't spend. Rewards are capped per title-session
and per user per day.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import config
from ..db import db
from ..ledger import credit
from ..security import get_user, get_user_optional
from ..util import now, now_iso, today, uid

router = APIRouter(prefix="/watch", tags=["watch-to-earn"])


class StartIn(BaseModel):
    content_id: str


class BeatIn(BaseModel):
    session_id: str
    position_sec: float = 0
    playing: bool = True


async def _earned_today(user_id: str) -> float:
    total = 0.0
    async for s in db.watch_sessions.find({"user_id": user_id, "day": today()}, {"rewarded": 1}):
        total += s.get("rewarded", 0.0)
    return total


@router.post("/start")
async def start(body: StartIn, user=Depends(get_user_optional)):
    c = await db.content.find_one({"id": body.content_id}, {"_id": 0, "id": 1, "title": 1})
    if not c:
        raise HTTPException(404, "Title not found")
    s = {"id": uid(), "content_id": c["id"], "user_id": user["id"] if user else None,
         "day": today(), "started_at": now_iso(), "last_beat_at": now_iso(),
         "verified_sec": 0.0, "rewarded": 0.0, "position_sec": 0}
    await db.watch_sessions.insert_one(s)
    await db.content.update_one({"id": c["id"]}, {"$inc": {"views": 1}})
    if user:
        entry = {"content_id": c["id"], "seconds": 0, "at": now_iso()}
        await db.users.update_one({"id": user["id"]},
                                  {"$push": {"watch_history": {"$each": [entry], "$position": 0, "$slice": 100}}})
    remaining = max(0.0, config.WATCH_REWARD_DAILY_CAP - await _earned_today(user["id"])) if user else 0.0
    return {"session_id": s["id"], "heartbeat_sec": config.HEARTBEAT_SEC, "earning": bool(user),
            "daily_remaining": round(remaining, 2)}


@router.post("/heartbeat")
async def heartbeat(body: BeatIn, user=Depends(get_user)):
    s = await db.watch_sessions.find_one({"id": body.session_id, "user_id": user["id"]})
    if not s:
        raise HTTPException(404, "Watch session not found")
    t = now()
    gap = (t - datetime.fromisoformat(s["last_beat_at"])).total_seconds()
    counted = min(max(gap, 0), config.HEARTBEAT_SEC * 1.5) if body.playing else 0.0
    verified = s["verified_sec"] + counted

    # Reward whole verified minutes, within per-title and daily caps. Replays behind a
    # pass earn nothing (points are spent on them, not farmed from them).
    content = await db.content.find_one({"id": s["content_id"]}, {"title": 1, "gated": 1})
    due = 0 if (content or {}).get("gated") else int(verified // 60) * config.WATCH_REWARD_PER_MIN
    due = min(due, config.WATCH_REWARD_CAP_PER_TITLE)
    reward = max(0.0, due - s["rewarded"])
    daily_left = max(0.0, config.WATCH_REWARD_DAILY_CAP - await _earned_today(user["id"]))
    reward = round(min(reward, daily_left), 4)

    await db.watch_sessions.update_one({"id": s["id"]}, {
        "$set": {"last_beat_at": t.isoformat(), "verified_sec": verified, "position_sec": body.position_sec},
        "$inc": {"rewarded": reward}})
    await db.users.update_one({"id": user["id"], "watch_history.content_id": s["content_id"]},
                              {"$set": {"watch_history.$.seconds": int(body.position_sec)}})
    if reward > 0:
        await credit(user["id"], reward, "watch_to_earn", f"Watched: {(content or {}).get('title', 'a title')}", ref=s["id"])
    from .campaigns import on_verified_watch      # campaign earning rules (e.g. watch the match preview)
    await on_verified_watch(user["id"], s["content_id"], verified)
    return {"earned_now": reward, "session_earned": round(s["rewarded"] + reward, 4),
            "verified_sec": round(verified), "daily_remaining": round(daily_left - reward, 2),
            "capped": s["rewarded"] + reward >= config.WATCH_REWARD_CAP_PER_TITLE}
