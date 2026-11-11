"""Sponsored replay-pass campaigns (commercial pilot).

A sponsor pays LoNo (ordinary currency, invoiced outside the app); fans earn $LONO
through a verified activity and redeem it for a limited replay pass; the organizer
is paid in currency; LoNo keeps a campaign fee. Built for one football match first,
and for other broadcasters, events and short courses later (the asset is any
LoNo-hosted title; the qualifying activity is any verified watch).

Money is recorded in `campaigns.financials` and never touches the points ledger.
Points move only through ledger.credit()/debit().

Claim = one consistent operation, as a state machine on `campaign_claims`
(unique per campaign + fan):
    pending → (reserve a pass: conditional $inc) → (debit points: conditional) → active
Any failed step undoes the earlier ones and marks the claim failed. A repeated
request returns the existing claim. Stale pending claims are repaired by
`repair_pending()`.
"""
import base64
import csv
import hashlib
import hmac
import io
import time
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from .. import config
from ..audit import audit
from ..db import db
from ..ledger import credit, log_tx
from ..security import get_admin, get_user
from ..storage import storage
from ..util import now, now_iso, uid

staff = APIRouter(prefix="/admin/campaigns", tags=["campaigns (staff)"])
fans = APIRouter(tags=["offers"])
replay = APIRouter(tags=["offers"])          # /api/replay/... protected media

VIEW_MIN_SEC = 30          # a "replay view" = a playback session with ≥30 s of verified watching
REPEAT_GAP_SEC = 3600      # a repeat visit starts at least an hour after the fan's first view


# ------------------------------------------------------------------ helpers
def _dt(s: str | None):
    return datetime.fromisoformat(s) if s else None


async def _campaign(cid: str) -> dict:
    c = await db.campaigns.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c


async def _history(c: dict, actor: dict, action: str, **details):
    entry = {"at": now_iso(), "by_id": actor.get("id"), "by_name": actor.get("name"), "action": action, "details": details}
    await db.campaigns.update_one({"id": c["id"]}, {"$push": {"history": entry}})
    await audit(f"campaign_{action}", actor, target=c["id"], details=details)


def _offer_view(c: dict) -> dict:
    """What a fan sees (no money, no internal notes)."""
    sponsor = c.get("_sponsor") or {}
    organizer = c.get("_organizer") or {}
    return {
        "id": c["id"], "title": c["title"], "description": c.get("description", ""), "status": c["status"],
        "sponsor": {"name": sponsor.get("name"), "logo_url": sponsor.get("logo_url")},
        "organizer": {"name": organizer.get("name")},
        "points_price": c["points_price"], "inventory_total": c["inventory_total"],
        "remaining": max(0, c.get("remaining", c["inventory_total"] - c.get("claimed", 0))),
        "opens_at": c["opens_at"], "closes_at": c["closes_at"], "access_days": c["access_days"],
        "replay": {"content_id": c["replay_content_id"], "title": c.get("_replay_title")},
        "earning_rule": c.get("earning_rule"),
    }


async def _with_partners(c: dict) -> dict:
    c["_sponsor"] = await db.partners.find_one({"id": c["sponsor_id"]}, {"_id": 0}) or {}
    c["_organizer"] = await db.partners.find_one({"id": c["organizer_id"]}, {"_id": 0}) or {}
    rc = await db.content.find_one({"id": c["replay_content_id"]}, {"_id": 0, "title": 1})
    c["_replay_title"] = (rc or {}).get("title")
    return c


def _is_claimable(c: dict, at: datetime | None = None) -> bool:
    at = at or now()
    return c["status"] == "open" and _dt(c["opens_at"]) <= at < _dt(c["closes_at"])


# ------------------------------------------------------------------ partners (organizers, sponsors)
class PartnerIn(BaseModel):
    kind: Literal["organizer", "sponsor"]
    name: str = Field(min_length=1, max_length=120)
    contact_email: str = Field(default="", max_length=200)
    logo_url: str = Field(default="", max_length=500)
    channel_id: str | None = None          # organizer's LoNo channel, if any


@staff.get("/partners")
async def partners(admin=Depends(get_admin)):
    return await db.partners.find({}, {"_id": 0}).sort("name", 1).to_list(500)


@staff.post("/partners")
async def add_partner(body: PartnerIn, admin=Depends(get_admin)):
    p = {"id": uid(), **body.model_dump(), "created_at": now_iso()}
    await db.partners.insert_one(dict(p))
    await audit("partner_added", admin, target=p["id"], details={"kind": p["kind"], "name": p["name"]})
    return p


# ------------------------------------------------------------------ campaigns (staff)
class Money(BaseModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    sponsor_payment: float = Field(ge=0)            # agreed amount the sponsor pays LoNo
    organizer_compensation: float = Field(ge=0)     # agreed amount LoNo pays the organizer
    lono_fee: float = Field(ge=0)                   # LoNo's campaign fee (agreed)
    direct_costs: list[dict] = Field(default_factory=list)   # [{"label": "...", "amount": 12.5}]


class EarningRule(BaseModel):
    content_id: str                                 # e.g. the match preview
    min_seconds: int = Field(ge=30, le=3600)        # verified watching in one session
    points: float = Field(gt=0, le=10000)


class CampaignIn(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(default="", max_length=2000)
    organizer_id: str
    sponsor_id: str
    replay_content_id: str
    earning_rule: EarningRule
    points_price: float = Field(gt=0, le=100000)
    inventory_total: int = Field(gt=0, le=1_000_000)
    opens_at: str
    closes_at: str
    access_days: int = Field(ge=1, le=365)
    report_window_days: int = Field(default=14, ge=1, le=180)
    financials: Money


class CampaignPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    earning_rule: EarningRule | None = None
    points_price: float | None = Field(default=None, gt=0)
    inventory_total: int | None = Field(default=None, gt=0)
    opens_at: str | None = None
    closes_at: str | None = None
    access_days: int | None = Field(default=None, ge=1, le=365)
    report_window_days: int | None = Field(default=None, ge=1, le=180)
    financials: Money | None = None


def _check_dates(opens: str, closes: str):
    try:
        o, cl = _dt(opens), _dt(closes)
    except ValueError:
        raise HTTPException(422, "Dates must be ISO times with a time zone")
    if not o.tzinfo or not cl.tzinfo:
        raise HTTPException(422, "Dates must include a time zone")
    if cl <= o:
        raise HTTPException(422, "The claim deadline must be after the opening time")


async def _protect_replay(content_id: str) -> dict:
    """Mark the replay title and its stored files as protected. Returns the content."""
    c = await db.content.find_one({"id": content_id}, {"_id": 0})
    if not c:
        raise HTTPException(422, "Replay title not found")
    url = c.get("stream_url") or ""
    if not url.startswith("/api/files/"):
        raise HTTPException(422, "The replay must be uploaded to LoNo (so its delivery can be protected). External links can't be protected.")
    path = url.removeprefix("/api/files/")
    prefix = path.rsplit("/", 1)[0] + "/" if path.endswith(".m3u8") else path   # HLS: protect its folder
    await db.files.update_many({"storage_path": {"$regex": "^" + _re_escape(prefix)}}, {"$set": {"protected": True}})
    await db.content.update_one({"id": content_id}, {"$set": {"gated": True, "media_prefix": prefix}})
    return {**c, "media_prefix": prefix}


def _re_escape(s: str) -> str:
    import re
    return re.escape(s)


@staff.get("")
async def list_campaigns(admin=Depends(get_admin)):
    out = []
    for c in await db.campaigns.find({}, {"_id": 0, "history": 0}).sort("created_at", -1).to_list(200):
        c = await _with_partners(c)
        out.append({**c, "sponsor_name": c["_sponsor"].get("name"), "organizer_name": c["_organizer"].get("name")})
    return [{k: v for k, v in c.items() if not k.startswith("_")} for c in out]


@staff.post("")
async def create_campaign(body: CampaignIn, admin=Depends(get_admin)):
    _check_dates(body.opens_at, body.closes_at)
    for pid, kind in ((body.organizer_id, "organizer"), (body.sponsor_id, "sponsor")):
        if not await db.partners.find_one({"id": pid, "kind": kind}):
            raise HTTPException(422, f"Unknown {kind}")
    if not await db.content.find_one({"id": body.earning_rule.content_id}):
        raise HTTPException(422, "The qualifying title (e.g. the match preview) wasn't found")
    if body.earning_rule.content_id == body.replay_content_id:
        raise HTTPException(422, "The qualifying activity can't be watching the replay itself")
    await _protect_replay(body.replay_content_id)
    c = {"id": uid(), **body.model_dump(), "status": "draft", "claimed": 0, "remaining": body.inventory_total,
         "confirmations": {"sponsor_payment": None, "distribution_permission": None, "playback_ready": None},
         "settlement": {"sponsor_invoice_ref": None, "sponsor_received": None, "organizer_paid": None},
         "rebooking": {"sponsor": "unknown", "organizer": "unknown", "notes": "", "updated_at": None},
         "history": [], "created_at": now_iso(), "created_by": admin["id"]}
    await db.campaigns.insert_one(dict(c))
    await _history(c, admin, "created", title=c["title"])
    return await get_campaign(c["id"], admin)


@staff.get("/{cid}")
async def get_campaign(cid: str, admin=Depends(get_admin)):
    c = await _with_partners(await _campaign(cid))
    return {**{k: v for k, v in c.items() if not k.startswith("_")},
            "sponsor": c["_sponsor"], "organizer": c["_organizer"], "replay_title": c["_replay_title"],
            "ready_to_open": _missing_to_open(c) == []}


@staff.patch("/{cid}")
async def update_campaign(cid: str, body: CampaignPatch, admin=Depends(get_admin)):
    c = await _campaign(cid)
    changes = body.model_dump(exclude_none=True)
    if c["status"] == "closed":
        raise HTTPException(409, "Closed campaigns can't be changed")
    if c["status"] != "draft":
        # Once open: only the deadline, inventory (not below what's claimed), report window and money records.
        locked = set(changes) - {"closes_at", "inventory_total", "report_window_days", "financials", "description"}
        if locked:
            raise HTTPException(409, f"Can't change {', '.join(sorted(locked))} after the campaign has opened")
    if "inventory_total" in changes and changes["inventory_total"] < c.get("claimed", 0):
        raise HTTPException(422, f"{c['claimed']} passes are already claimed")
    _check_dates(changes.get("opens_at", c["opens_at"]), changes.get("closes_at", c["closes_at"]))
    inc = {}
    if "inventory_total" in changes:      # keep the remaining counter in step (atomic, alongside claims)
        inc = {"remaining": changes["inventory_total"] - c["inventory_total"]}
    await db.campaigns.update_one({"id": cid}, {"$set": changes, **({"$inc": inc} if inc else {})})
    await _history(c, admin, "updated", fields=sorted(changes))
    return await get_campaign(cid, admin)


class ConfirmIn(BaseModel):
    item: Literal["sponsor_payment", "distribution_permission", "playback_ready"]
    reference: str = Field(default="", max_length=200)      # payment/bank ref, contract ref
    amount: float | None = Field(default=None, ge=0)        # sponsor payment received
    note: str = Field(default="", max_length=500)


async def _playback_check(c: dict) -> list[str]:
    """Server-side readiness: the replay is LoNo-hosted, protected and its file exists."""
    problems = []
    rc = await db.content.find_one({"id": c["replay_content_id"]}, {"_id": 0})
    if not rc:
        return ["Replay title is missing"]
    url = rc.get("stream_url") or ""
    if not url.startswith("/api/files/"):
        problems.append("Replay isn't stored on LoNo")
    else:
        path = url.removeprefix("/api/files/")
        f = await db.files.find_one({"storage_path": path, "is_deleted": False})
        if not f:
            problems.append("Replay file record is missing")
        elif not f.get("protected"):
            problems.append("Replay file isn't protected")
        elif not await storage.exists(path):
            problems.append("Replay file isn't in storage")
    if not rc.get("gated"):
        problems.append("Replay title isn't gated")
    return problems


@staff.post("/{cid}/confirm")
async def confirm(cid: str, body: ConfirmIn, admin=Depends(get_admin)):
    c = await _campaign(cid)
    if body.item == "sponsor_payment":
        if not body.reference or body.amount is None:
            raise HTTPException(422, "Record the payment reference and the amount received")
        if body.amount < c["financials"]["sponsor_payment"]:
            raise HTTPException(422, f"Received {body.amount} is less than the agreed {c['financials']['sponsor_payment']}")
    if body.item == "distribution_permission" and not body.reference:
        raise HTTPException(422, "Record the agreement or permission reference")
    if body.item == "playback_ready":
        problems = await _playback_check(c)
        if problems:
            raise HTTPException(409, "Playback isn't ready: " + "; ".join(problems))
    rec = {"by_id": admin["id"], "by_name": admin.get("name"), "at": now_iso(), "reference": body.reference,
           "amount": body.amount, "note": body.note}
    sets = {f"confirmations.{body.item}": rec}
    if body.item == "sponsor_payment":
        sets["settlement.sponsor_received"] = {"amount": body.amount, "reference": body.reference, "at": rec["at"]}
    await db.campaigns.update_one({"id": cid}, {"$set": sets})
    await _history(c, admin, f"confirmed_{body.item}", reference=body.reference, amount=body.amount)
    return await get_campaign(cid, admin)


def _missing_to_open(c: dict) -> list[str]:
    missing = [k.replace("_", " ") for k, v in c["confirmations"].items() if not v]
    if _dt(c["closes_at"]) <= now():
        missing.append("a claim deadline in the future")
    return missing


@staff.post("/{cid}/open")
async def open_campaign(cid: str, admin=Depends(get_admin)):
    c = await _campaign(cid)
    if c["status"] not in ("draft",):
        raise HTTPException(409, f"The campaign is {c['status']}")
    missing = _missing_to_open(c)
    if missing:
        raise HTTPException(409, "Can't open yet. Missing: " + ", ".join(missing))
    problems = await _playback_check(c)          # re-check at the moment of opening
    if problems:
        raise HTTPException(409, "Playback isn't ready: " + "; ".join(problems))
    res = await db.campaigns.update_one({"id": cid, "status": "draft"}, {"$set": {"status": "open", "opened_at": now_iso()}})
    if res.modified_count:
        await _history(c, admin, "opened")
    return await get_campaign(cid, admin)


@staff.post("/{cid}/pause")
async def pause(cid: str, admin=Depends(get_admin)):
    c = await _campaign(cid)
    if (await db.campaigns.update_one({"id": cid, "status": "open"}, {"$set": {"status": "paused"}})).modified_count:
        await _history(c, admin, "paused")
    return await get_campaign(cid, admin)


@staff.post("/{cid}/resume")
async def resume(cid: str, admin=Depends(get_admin)):
    c = await _campaign(cid)
    if (await db.campaigns.update_one({"id": cid, "status": "paused"}, {"$set": {"status": "open"}})).modified_count:
        await _history(c, admin, "resumed")
    return await get_campaign(cid, admin)


@staff.post("/{cid}/close")
async def close(cid: str, admin=Depends(get_admin)):
    """Stops new claims. Passes already claimed keep their access period."""
    c = await _campaign(cid)
    if (await db.campaigns.update_one({"id": cid, "status": {"$in": ["draft", "open", "paused"]}},
                                      {"$set": {"status": "closed", "closed_at": now_iso()}})).modified_count:
        await _history(c, admin, "closed")
    return await get_campaign(cid, admin)


class SettlementIn(BaseModel):
    sponsor_invoice_ref: str | None = Field(default=None, max_length=200)
    organizer_paid_amount: float | None = Field(default=None, ge=0)
    organizer_paid_reference: str | None = Field(default=None, max_length=200)
    direct_costs: list[dict] | None = None      # actual direct costs [{"label", "amount"}]


@staff.post("/{cid}/settlement")
async def settlement(cid: str, body: SettlementIn, admin=Depends(get_admin)):
    c = await _campaign(cid)
    sets = {}
    if body.sponsor_invoice_ref is not None:
        sets["settlement.sponsor_invoice_ref"] = body.sponsor_invoice_ref
    if body.organizer_paid_amount is not None:
        if not body.organizer_paid_reference:
            raise HTTPException(422, "Record the payment reference for the organizer")
        sets["settlement.organizer_paid"] = {"amount": body.organizer_paid_amount, "reference": body.organizer_paid_reference,
                                             "at": now_iso(), "by_name": admin.get("name")}
    if body.direct_costs is not None:
        for d in body.direct_costs:
            if not isinstance(d.get("amount"), (int, float)) or d["amount"] < 0 or not d.get("label"):
                raise HTTPException(422, "Each direct cost needs a label and a non-negative amount")
        sets["financials.direct_costs"] = body.direct_costs
    if sets:
        await db.campaigns.update_one({"id": cid}, {"$set": sets})
        await _history(c, admin, "settlement_recorded", **{k.split(".")[-1]: (v if not isinstance(v, dict) else v.get("reference")) for k, v in sets.items() if k != "financials.direct_costs"})
    return await get_campaign(cid, admin)


class RebookingIn(BaseModel):
    sponsor: Literal["unknown", "yes", "no", "in_talks"] = "unknown"
    organizer: Literal["unknown", "yes", "no", "in_talks"] = "unknown"
    notes: str = Field(default="", max_length=1000)


@staff.put("/{cid}/rebooking")
async def rebooking(cid: str, body: RebookingIn, admin=Depends(get_admin)):
    c = await _campaign(cid)
    await db.campaigns.update_one({"id": cid}, {"$set": {"rebooking": {**body.model_dump(), "updated_at": now_iso(), "by_name": admin.get("name")}}})
    await _history(c, admin, "rebooking_recorded", sponsor=body.sponsor, organizer=body.organizer)
    return await get_campaign(cid, admin)


# ------------------------------------------------------------------ claims (fans)
async def _release_inventory(cid: str):
    await db.campaigns.update_one({"id": cid, "claimed": {"$gt": 0}}, {"$inc": {"claimed": -1, "remaining": 1}})


def _is_dup(e: Exception) -> bool:
    return "duplicate" in type(e).__name__.lower() or "E11000" in str(e)


async def claim_pass(c: dict, user: dict) -> dict:
    """Points deduction + pass allocation + access as one operation (see module docstring)."""
    key = {"campaign_id": c["id"], "user_id": user["id"]}
    attempt = uid()
    pending = {"id": uid(), **key, "status": "pending", "attempt": attempt, "points": c["points_price"],
               "created_at": now_iso(), "updated_at": now_iso()}
    try:
        await db.campaign_claims.insert_one(dict(pending))
        claim = pending
    except Exception as e:                           # unique (campaign, user): an earlier claim exists
        if not _is_dup(e):
            raise
        claim = await db.campaign_claims.find_one(key, {"_id": 0})
        if claim["status"] == "active":
            return claim                             # repeated click / network retry: same claim, no second deduction
        if claim["status"] == "pending":
            raise HTTPException(409, "Your claim is being processed. Try again in a moment.")
        # failed or reversed before: take it over for a fresh attempt (only one request can)
        res = await db.campaign_claims.update_one({**key, "status": claim["status"], "attempt": claim.get("attempt")},
                                                  {"$set": {"status": "pending", "attempt": attempt, "points": c["points_price"],
                                                            "updated_at": now_iso(), "failure": None}})
        if not res.modified_count:
            raise HTTPException(409, "Your claim is being processed. Try again in a moment.")
        claim = {**claim, "status": "pending", "attempt": attempt}

    async def fail(reason: str, status: int, msg: str):
        await db.campaign_claims.update_one({"id": claim["id"], "attempt": attempt},
                                            {"$set": {"status": "failed", "failure": reason, "updated_at": now_iso()}})
        raise HTTPException(status, msg)

    # 1) reserve a pass: succeeds only while the offer is open and a pass is left
    t = now_iso()
    res = await db.campaigns.update_one(
        {"id": c["id"], "status": "open", "opens_at": {"$lte": t}, "closes_at": {"$gt": t}, "remaining": {"$gt": 0}},
        {"$inc": {"remaining": -1, "claimed": 1}})
    if not res.modified_count:
        fresh = await db.campaigns.find_one({"id": c["id"]}, {"status": 1, "remaining": 1})
        if fresh and fresh["status"] == "open" and fresh.get("remaining", 0) <= 0:
            await fail("sold_out", 409, "All passes have been claimed. Your points weren't used.")
        await fail("not_open", 409, "This offer isn't open for claims right now. Your points weren't used.")

    # 2) deduct points: succeeds only if the balance covers the price
    res = await db.users.update_one({"id": user["id"], "wallet.lono_balance": {"$gte": c["points_price"]}},
                                    {"$inc": {"wallet.lono_balance": -c["points_price"]}})
    if not res.modified_count:
        await _release_inventory(c["id"])
        await fail("insufficient_points", 402, f"You need {c['points_price']:g} $LONO for this pass.")
    tx = await log_tx(user["id"], "pass_claim", -c["points_price"], f"Replay pass: {c['title']}", ref=claim["id"])

    # 3) activate: access runs from now for the campaign's access period
    expires = (now() + timedelta(days=c["access_days"])).isoformat()
    await db.campaign_claims.update_one({"id": claim["id"], "attempt": attempt},
                                        {"$set": {"status": "active", "claimed_at": now_iso(), "expires_at": expires,
                                                  "tx_id": tx["id"], "updated_at": now_iso()}})
    return await db.campaign_claims.find_one({"id": claim["id"]}, {"_id": 0})


async def repair_pending(max_age_sec: int | None = None) -> int:
    """Finish or undo claims left 'pending' by a crash. Safe to run any time."""
    max_age = max_age_sec if max_age_sec is not None else config.CLAIM_PENDING_TIMEOUT_SEC
    cutoff = (now() - timedelta(seconds=max_age)).isoformat()
    fixed = 0
    async for cl in db.campaign_claims.find({"status": "pending", "updated_at": {"$lt": cutoff}}, {"_id": 0}):
        tx = await db.transactions.find_one({"ref": cl["id"], "kind": "pass_claim", "at": {"$gte": cl["updated_at"]}})
        c = await db.campaigns.find_one({"id": cl["campaign_id"]}, {"_id": 0})
        if tx:   # points were taken: complete the claim
            expires = (_dt(tx["at"]) + timedelta(days=c["access_days"])).isoformat()
            await db.campaign_claims.update_one({"id": cl["id"], "status": "pending"},
                                                {"$set": {"status": "active", "claimed_at": tx["at"], "expires_at": expires, "tx_id": tx["id"],
                                                          "repaired": True, "updated_at": now_iso()}})
        else:    # points not taken: release a pass if one may have been reserved
            active = await db.campaign_claims.count_documents({"campaign_id": cl["campaign_id"], "status": "active"})
            if c and c.get("claimed", 0) > active:
                await _release_inventory(cl["campaign_id"])
            await db.campaign_claims.update_one({"id": cl["id"], "status": "pending"},
                                                {"$set": {"status": "failed", "failure": "interrupted", "updated_at": now_iso()}})
        fixed += 1
    return fixed


def _claim_view(cl: dict) -> dict:
    return {k: cl.get(k) for k in ("id", "campaign_id", "status", "points", "claimed_at", "expires_at", "failure")}


@fans.get("/offers")
async def offers(user=Depends(get_user)):
    t = now_iso()
    items = await db.campaigns.find({"status": "open", "opens_at": {"$lte": t}, "closes_at": {"$gt": t}}, {"_id": 0}).to_list(50)
    out = []
    for c in items:
        v = _offer_view(await _with_partners(c))
        cl = await db.campaign_claims.find_one({"campaign_id": c["id"], "user_id": user["id"], "status": "active"}, {"_id": 0})
        v["my_claim"] = _claim_view(cl) if cl else None
        v["my_progress"] = await _progress(c, user)
        out.append(v)
    return out


async def _progress(c: dict, user: dict) -> dict:
    rule = c["earning_rule"]
    earned = await db.campaign_earnings.find_one({"campaign_id": c["id"], "user_id": user["id"]})
    best = 0.0
    async for s in db.watch_sessions.find({"user_id": user["id"], "content_id": rule["content_id"]}, {"verified_sec": 1}):
        best = max(best, s.get("verified_sec", 0))
    preview = await db.content.find_one({"id": rule["content_id"]}, {"_id": 0, "title": 1, "id": 1})
    return {"earned": bool(earned), "verified_sec": round(min(best, rule["min_seconds"])), "min_seconds": rule["min_seconds"],
            "points": rule["points"], "content": preview}


@fans.get("/offers/{cid}")
async def offer(cid: str, user=Depends(get_user)):
    c = await _campaign(cid)
    if c["status"] == "draft":
        raise HTTPException(404, "Offer not found")
    v = _offer_view(await _with_partners(c))
    cl = await db.campaign_claims.find_one({"campaign_id": cid, "user_id": user["id"], "status": "active"}, {"_id": 0})
    u = await db.users.find_one({"id": user["id"]}, {"wallet": 1})
    return {**v, "claimable": _is_claimable(c), "my_claim": _claim_view(cl) if cl else None,
            "my_balance": round(u["wallet"]["lono_balance"], 4), "my_progress": await _progress(c, user)}


@fans.post("/offers/{cid}/claim")
async def claim(cid: str, user=Depends(get_user)):
    c = await _campaign(cid)
    if c["status"] == "draft":
        raise HTTPException(404, "Offer not found")
    cl = await claim_pass(c, user)
    return {"claim": _claim_view(cl), "offer": _offer_view(await _with_partners(await _campaign(cid)))}


@fans.get("/me/passes")
async def my_passes(user=Depends(get_user)):
    out = []
    async for cl in db.campaign_claims.find({"user_id": user["id"], "status": "active"}, {"_id": 0}).sort("claimed_at", -1):
        c = await _with_partners(await _campaign(cl["campaign_id"]))
        rc = await db.content.find_one({"id": c["replay_content_id"]}, {"_id": 0, "title": 1, "thumbnail_url": 1, "duration_sec": 1})
        out.append({**_claim_view(cl), "valid": _dt(cl["expires_at"]) > now(), "campaign_title": c["title"],
                    "sponsor": c["_sponsor"].get("name"), "replay": {"content_id": c["replay_content_id"], **(rc or {})}})
    return out


# ------------------------------------------------------------------ protected replay playback
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _mac(msg: str) -> str:
    return _b64(hmac.new(("replay:" + config.JWT_SECRET).encode(), msg.encode(), hashlib.sha256).digest())[:32]


def make_token(claim_id: str, user_id: str, prefix: str, exp: int) -> str:
    body = f"{claim_id}|{user_id}|{prefix}|{exp}"
    return _b64(body.encode()) + "." + _mac(body)


def read_token(tok: str) -> tuple[str, str, str, int] | None:
    try:
        b64, mac = tok.split(".", 1)
        body = _unb64(b64).decode()
        if not hmac.compare_digest(_mac(body), mac):
            return None
        claim_id, user_id, prefix, exp = body.split("|")
        return claim_id, user_id, prefix, int(exp)
    except (ValueError, UnicodeDecodeError):
        return None


COOKIE = "lono_replay"


@fans.post("/me/passes/{claim_id}/play")
async def play(claim_id: str, request: Request, user=Depends(get_user)):
    """Issue a playback URL for this fan's pass. The URL only works together with a
    cookie bound to the same fan, so a shared link doesn't play elsewhere."""
    cl = await db.campaign_claims.find_one({"id": claim_id, "user_id": user["id"], "status": "active"}, {"_id": 0})
    if not cl:
        raise HTTPException(404, "Pass not found")
    if _dt(cl["expires_at"]) <= now():
        raise HTTPException(410, "This pass's access period has ended")
    c = await _campaign(cl["campaign_id"])
    rc = await db.content.find_one({"id": c["replay_content_id"]}, {"_id": 0})
    path = rc["stream_url"].removeprefix("/api/files/")
    exp = int(time.time()) + config.REPLAY_TOKEN_TTL_SEC
    tok = make_token(cl["id"], user["id"], rc.get("media_prefix") or path, exp)
    resp_body = {"url": f"/api/replay/{tok}/{path}", "expires_at": exp, "content_id": rc["id"], "title": rc["title"],
                 "poster": rc.get("thumbnail_url"), "access_until": cl["expires_at"]}
    import json
    resp = Response(json.dumps(resp_body), media_type="application/json")
    cookie_val = make_token(cl["id"], user["id"], "cookie", exp)
    resp.set_cookie(COOKIE, cookie_val, max_age=config.REPLAY_TOKEN_TTL_SEC, httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", path="/api/replay")
    return resp


async def _entitled(claim_id: str, user_id: str) -> bool:
    cl = await db.campaign_claims.find_one({"id": claim_id, "user_id": user_id, "status": "active"}, {"expires_at": 1})
    return bool(cl and _dt(cl["expires_at"]) > now())


@replay.get("/replay/{token}/{path:path}")
async def replay_media(token: str, path: str, request: Request):
    t = read_token(token)
    if not t:
        raise HTTPException(403, "This replay link isn't valid")
    claim_id, user_id, prefix, exp = t
    if exp < time.time():
        raise HTTPException(403, "This replay link has expired. Open the replay from My passes again.")
    ck = read_token(request.cookies.get(COOKIE, ""))
    if not ck or ck[0] != claim_id or ck[1] != user_id or ck[3] < time.time():
        raise HTTPException(403, "This replay can only be watched by the fan who claimed the pass, from My passes.")
    if not (path == prefix or (prefix.endswith("/") and path.startswith(prefix))) or ".." in path:
        raise HTTPException(403, "Not part of this replay")
    if not await _entitled(claim_id, user_id):
        raise HTTPException(403, "This pass is no longer active")
    f = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not f:
        raise HTTPException(404, "Not found")
    # Object storage: a 2-minute signed link (the pass is re-checked on every request here).
    resp = await storage.serve(path, f.get("content_type", "application/octet-stream"), request, ttl=120)
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


# ------------------------------------------------------------------ staff: claims and reversals
@staff.get("/{cid}/claims")
async def claims(cid: str, admin=Depends(get_admin)):
    await _campaign(cid)
    out = []
    async for cl in db.campaign_claims.find({"campaign_id": cid}, {"_id": 0}).sort("created_at", -1):
        u = await db.users.find_one({"id": cl["user_id"]}, {"name": 1, "email": 1})
        out.append({**cl, "fan_name": (u or {}).get("name"), "fan_email": (u or {}).get("email")})
    return out


class ReverseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    return_pass: bool = True


@staff.post("/{cid}/claims/{claim_id}/reverse")
async def reverse(cid: str, claim_id: str, body: ReverseIn, admin=Depends(get_admin)):
    """Refund a failed or canceled redemption: points back exactly once; the pass goes
    back to inventory only if the offer is still open (and staff want it reused)."""
    c = await _campaign(cid)
    res = await db.campaign_claims.update_one(
        {"id": claim_id, "campaign_id": cid, "status": "active"},
        {"$set": {"status": "reversed", "reversed_at": now_iso(), "reversed_by": admin.get("name"), "reverse_reason": body.reason,
                  "updated_at": now_iso()}})
    if not res.modified_count:
        cl = await db.campaign_claims.find_one({"id": claim_id, "campaign_id": cid}, {"_id": 0})
        if cl and cl["status"] == "reversed":
            return {"claim": _claim_view(cl), "refunded": 0, "pass_returned": cl.get("pass_returned", False), "already_reversed": True}
        raise HTTPException(409, "Only active passes can be reversed")
    cl = await db.campaign_claims.find_one({"id": claim_id}, {"_id": 0})
    await credit(cl["user_id"], cl["points"], "pass_refund", f"Refund: {c['title']} ({body.reason})", ref=claim_id, earned=False)
    returned = False
    if body.return_pass and _is_claimable(c):
        await _release_inventory(cid)
        returned = True
    await db.campaign_claims.update_one({"id": claim_id}, {"$set": {"pass_returned": returned}})
    await _history(c, admin, "claim_reversed", claim_id=claim_id, points=cl["points"], pass_returned=returned, reason=body.reason)
    return {"claim": _claim_view(cl), "refunded": cl["points"], "pass_returned": returned}


# ------------------------------------------------------------------ earning rule (verified viewing)
async def on_verified_watch(user_id: str, content_id: str, verified_sec: float):
    """Called by the watch heartbeat. Awards each open campaign's earning bonus once per fan."""
    t = now_iso()
    async for c in db.campaigns.find({"status": "open", "earning_rule.content_id": content_id,
                                      "opens_at": {"$lte": t}, "closes_at": {"$gt": t}}, {"_id": 0}):
        rule = c["earning_rule"]
        if verified_sec < rule["min_seconds"]:
            continue
        try:   # unique (campaign, user): exactly once
            await db.campaign_earnings.insert_one({"id": uid(), "campaign_id": c["id"], "user_id": user_id, "points": rule["points"], "at": t})
        except Exception as e:
            if _is_dup(e):
                continue
            raise
        await credit(user_id, rule["points"], "campaign_reward", f"Earned for {c['title']}: watched the qualifying title", ref=c["id"])


# ------------------------------------------------------------------ reports
async def _viewing(c: dict) -> dict:
    window_end = None
    sessions = await db.watch_sessions.find({"content_id": c["replay_content_id"], "user_id": {"$ne": None},
                                             "verified_sec": {"$gte": VIEW_MIN_SEC}}, {"_id": 0}).to_list(100000)
    entitled = {cl["user_id"] async for cl in db.campaign_claims.find({"campaign_id": c["id"], "status": "active"}, {"user_id": 1})}
    by_user: dict[str, list] = {}
    for s in sessions:
        if s["user_id"] in entitled:
            by_user.setdefault(s["user_id"], []).append(s)
    window = timedelta(days=c.get("report_window_days", 14))
    repeat = 0
    for views in by_user.values():
        views.sort(key=lambda s: s["started_at"])
        first = _dt(views[0]["started_at"])
        window_end = first + window
        if any(REPEAT_GAP_SEC <= (_dt(v["started_at"]) - first).total_seconds() and _dt(v["started_at"]) <= window_end for v in views[1:]):
            repeat += 1
    total_min = sum(v["verified_sec"] for vs in by_user.values() for v in vs) / 60
    return {"unique_viewers": len(by_user), "views": sum(len(v) for v in by_user.values()),
            "repeat_viewers": repeat, "watch_minutes": round(total_min, 1)}


def _money(c: dict) -> dict:
    f, st = c["financials"], c["settlement"]
    agreed_costs = sum(float(d.get("amount", 0)) for d in f.get("direct_costs", []))
    received = (st.get("sponsor_received") or {}).get("amount")
    org_paid = (st.get("organizer_paid") or {}).get("amount")
    contribution = (received or 0) - (org_paid if org_paid is not None else f["organizer_compensation"]) - agreed_costs
    return {"currency": f["currency"], "sponsor_payment_agreed": f["sponsor_payment"], "sponsor_payment_received": received,
            "sponsor_payment_reference": (st.get("sponsor_received") or {}).get("reference"),
            "sponsor_invoice_reference": st.get("sponsor_invoice_ref"),
            "organizer_compensation_agreed": f["organizer_compensation"], "organizer_paid": org_paid,
            "organizer_payment_reference": (st.get("organizer_paid") or {}).get("reference"),
            "lono_fee_agreed": f["lono_fee"], "direct_costs": f.get("direct_costs", []), "direct_costs_total": round(agreed_costs, 2),
            "contribution_after_direct_costs": round(contribution, 2),
            "covers_direct_costs": contribution >= 0 and received is not None,
            "fee_variance": round(contribution - f["lono_fee"], 2)}


async def _reconcile(c: dict) -> dict:
    claims_ = await db.campaign_claims.find({"campaign_id": c["id"]}, {"_id": 0}).to_list(100000)
    ids = [cl["id"] for cl in claims_]
    debits = refunds = 0.0
    async for t in db.transactions.find({"ref": {"$in": ids}, "kind": {"$in": ["pass_claim", "pass_refund"]}}, {"kind": 1, "amount": 1}):
        if t["kind"] == "pass_claim":
            debits += -t["amount"]
        else:
            refunds += t["amount"]
    active = [cl for cl in claims_ if cl["status"] == "active"]
    expected_points = sum(cl["points"] for cl in active)
    returned_passes = sum(1 for cl in claims_ if cl["status"] == "reversed" and cl.get("pass_returned"))
    kept_reversed = sum(1 for cl in claims_ if cl["status"] == "reversed" and not cl.get("pass_returned"))
    points_ok = abs((debits - refunds) - expected_points) < 1e-6
    inventory_ok = c.get("claimed", 0) == len(active) + kept_reversed and c.get("remaining", 0) + c.get("claimed", 0) == c["inventory_total"]
    earned = 0.0
    async for e in db.campaign_earnings.find({"campaign_id": c["id"]}, {"points": 1}):
        earned += e["points"]
    ledger_earned = 0.0
    async for t in db.transactions.find({"ref": c["id"], "kind": "campaign_reward"}, {"amount": 1}):
        ledger_earned += t["amount"]
    m = _money(c)
    cash_ok = m["sponsor_payment_received"] is not None and m["sponsor_payment_received"] >= m["sponsor_payment_agreed"] and \
        (m["organizer_paid"] is None or abs(m["organizer_paid"] - m["organizer_compensation_agreed"]) < 0.005)
    return {"points_debited": round(debits, 4), "points_refunded": round(refunds, 4), "points_net": round(debits - refunds, 4),
            "points_expected_from_active_passes": round(expected_points, 4), "points_ok": points_ok,
            "inventory_counter": c.get("claimed", 0), "active_passes": len(active), "reversed_passes_returned": returned_passes,
            "reversed_passes_not_returned": kept_reversed, "inventory_ok": inventory_ok,
            "campaign_points_awarded": round(earned, 4), "campaign_points_in_ledger": round(ledger_earned, 4),
            "earnings_ok": abs(earned - ledger_earned) < 1e-6, "cash_ok": cash_ok,
            "pending_claims": sum(1 for cl in claims_ if cl["status"] == "pending"),
            "all_ok": points_ok and inventory_ok and abs(earned - ledger_earned) < 1e-6 and cash_ok}


@staff.get("/{cid}/report")
async def report(cid: str, admin=Depends(get_admin)):
    c = await _campaign(cid)
    active = await db.campaign_claims.count_documents({"campaign_id": cid, "status": "active"})
    reversed_ = await db.campaign_claims.count_documents({"campaign_id": cid, "status": "reversed"})
    failed = await db.campaign_claims.count_documents({"campaign_id": cid, "status": "failed"})
    earners = await db.campaign_earnings.count_documents({"campaign_id": cid})
    v = await _viewing(c)
    return {"campaign_id": cid, "title": c["title"], "status": c["status"], "report_window_days": c.get("report_window_days", 14),
            "passes": {"available": c["inventory_total"], "claimed": active, "remaining": max(0, c.get("remaining", 0)),
                       "reversed": reversed_, "failed_attempts": failed},
            "fans_who_earned": earners, "viewing": v,
            "claim_to_view_rate": round(v["unique_viewers"] / active, 3) if active else 0.0,
            "money": _money(c), "reconciliation": await _reconcile(c), "rebooking": c.get("rebooking")}


async def _sponsor_report(c: dict) -> dict:
    c = await _with_partners(c)
    active = await db.campaign_claims.count_documents({"campaign_id": c["id"], "status": "active"})
    v = await _viewing(c)
    return {"campaign": c["title"], "sponsor": c["_sponsor"].get("name"), "organizer": c["_organizer"].get("name"),
            "offer_period": f"{c['opens_at']} to {c['closes_at']}", "passes_offered": c["inventory_total"],
            "passes_claimed": active, "fans_who_watched_the_replay": v["unique_viewers"],
            "claimed_but_not_yet_watched": max(0, active - v["unique_viewers"]),
            "replay_views": v["views"], "fans_who_came_back": v["repeat_viewers"],
            "total_watch_minutes": v["watch_minutes"], "fans_who_earned_points": await db.campaign_earnings.count_documents({"campaign_id": c["id"]}),
            "rebooked": {"sponsor": c["rebooking"]["sponsor"], "organizer": c["rebooking"]["organizer"]},
            "definitions": {"claimed": "A fan redeemed points for a pass.",
                            "watched": f"A fan with a pass played the replay for at least {VIEW_MIN_SEC} seconds (server-verified).",
                            "came back": f"Watched again at least an hour after their first view, within {c.get('report_window_days', 14)} days."}}


@staff.get("/{cid}/sponsor-report")
async def sponsor_report(cid: str, admin=Depends(get_admin)):
    return await _sponsor_report(await _campaign(cid))


@staff.get("/{cid}/sponsor-report.csv")
async def sponsor_report_csv(cid: str, admin=Depends(get_admin)):
    r = await _sponsor_report(await _campaign(cid))
    def cell(v):
        v = "" if v is None else str(v)
        return "'" + v if v[:1] in ("=", "+", "-", "@") and not v.lstrip("-").replace(".", "", 1).isdigit() else v
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Metric", "Value"])
    for k, val in r.items():
        if isinstance(val, dict):
            for k2, v2 in val.items():
                w.writerow([cell(f"{k}: {k2}".replace("_", " ")), cell(v2)])
        else:
            w.writerow([cell(k.replace("_", " ")), cell(val)])
    data = buf.getvalue()
    return Response(data, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="sponsor-report-{cid[:8]}.csv"'})
