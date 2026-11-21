from datetime import timedelta
from typing import Literal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from ..db import db
from ..security import get_user, get_admin
from ..audit import audit
from ..util import now, now_iso, uid

router = APIRouter(prefix="/creator", tags=["creator"])
review_router = APIRouter(prefix="/admin/creators", tags=["creator verification"])


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=4000)
    kind: Literal["movie", "series", "short", "music", "podcast", "live_tv", "live_radio", "course"]
    category: str = Field(min_length=1, max_length=60)
    thumbnail_url: str
    stream_url: str
    duration_sec: int = 0
    is_original: bool = False
    is_premium: bool = False


async def _channel_for(user) -> dict:
    ch = await db.channels.find_one({"owner_id": user["id"]}, {"_id": 0})
    if ch:
        return ch
    ch = {
        "id": str(uuid5(NAMESPACE_URL, f"lono:channel:{user['id']}")), "owner_id": user["id"], "name": f"{user['name']}'s channel",
        "handle": f"@{''.join(x for x in user['name'].lower() if x.isalnum())}_{user['id'][:4]}",
        "banner_url": "https://images.unsplash.com/photo-1655947717064-d856af599bd1?crop=entropy&cs=srgb&fm=jpg&q=85",
        "avatar_url": user["avatar_url"], "bio": "New creator on LoNo", "subscribers": 0,
        "created_at": now_iso(),
    }
    try:
        await db.channels.insert_one(ch)
    except DuplicateKeyError:
        existing = await db.channels.find_one({"owner_id": user["id"]}, {"_id": 0})
        if existing:
            return existing
        raise
    ch.pop("_id", None)
    return ch


class CreatorProfileIn(BaseModel):
    classification: Literal["individual", "university", "media", "religious", "commercial", "community", "other"] = "individual"
    organization: str = Field(default="", max_length=160)
    country: str = Field(default="", max_length=80)
    website: str = Field(default="", max_length=500)
    verification_note: str = Field(default="", max_length=1000)


class ChannelProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    bio: str = Field(default="", max_length=1500)
    avatar_url: str = Field(default="", max_length=1000)
    banner_url: str = Field(default="", max_length=1000)


class CreatorReviewIn(BaseModel):
    decision: Literal["verified", "changes_requested", "revoked"]
    reason: str = Field(min_length=3, max_length=500)
    revision: int = Field(ge=0)


def _https(value):
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


async def _branding_image(value, user):
    if not value or _https(value):
        return
    if value.startswith("/api/files/uploads/") and await db.files.find_one({"storage_path": value.removeprefix("/api/files/"), "user_id": user["id"], "content_type": {"$regex": "^image/"}, "is_deleted": False, "pending": {"$ne": True}, "protected": {"$ne": True}}):
        return
    raise HTTPException(422, "Use an HTTPS image or an image uploaded to your account")


def _revision(ch):
    value = ch.get("creator_revision", 0)
    return {"creator_revision": value} if value else {"$or": [{"creator_revision": 0}, {"creator_revision": {"$exists": False}}]}


async def _update_creator(ch, fields):
    result = await db.channels.update_one({"id": ch["id"], **_revision(ch)}, {"$set": fields, "$inc": {"creator_revision": 1}})
    if not result.matched_count:
        raise HTTPException(409, "Creator profile changed; reload and retry")


@router.get("/profile")
async def creator_profile(user=Depends(get_user)):
    return await _channel_for(user)


@router.put("/profile")
async def save_creator_profile(body: CreatorProfileIn, user=Depends(get_user)):
    ch = await _channel_for(user)
    data = {k: v.strip() for k,v in body.model_dump().items()}
    if data["classification"] != "individual" and not data["organization"]:
        raise HTTPException(422, "Enter the organization name")
    if data["website"] and not _https(data["website"]):
        raise HTTPException(422, "Enter an HTTPS website")
    fields = {"creator_profile": data, "creator_classification": data["classification"]}
    if data != ch.get("creator_profile"):
        fields.update({"verification_status": "unverified", "verification_reason": "", "verification_submitted_at": None})
    await _update_creator(ch, fields)
    await audit("creator_profile_saved", user, target=ch["id"])
    return await _channel_for(user)


@router.put("/channel")
async def save_channel(body: ChannelProfileIn, user=Depends(get_user)):
    ch = await _channel_for(user)
    data = {k:v.strip() for k,v in body.model_dump().items()}
    if len(data["name"])<2:
        raise HTTPException(422, "Enter a channel name")
    for field in ("avatar_url", "banner_url"):
        await _branding_image(data[field],user)
    if data["name"] != ch["name"]:
        data.update({"verification_status": "unverified", "verification_reason": "", "verification_submitted_at": None})
    await _update_creator(ch,data)
    await audit("channel_branding_saved", user, target=ch["id"])
    return await _channel_for(user)


@router.post("/verification/submit")
async def submit_verification(user=Depends(get_user)):
    ch = await _channel_for(user)
    profile = ch.get("creator_profile") or {}
    if not profile.get("country") or not profile.get("verification_note"):
        raise HTTPException(422, "Complete country and verification details first")
    if ch.get("verification_status") in ("pending", "verified"):
        raise HTTPException(409, "Verification is already pending or approved")
    await _update_creator(ch,{"verification_status":"pending","verification_submitted_at":now_iso(),"verification_reason":""})
    await audit("creator_verification_submitted",user,target=ch["id"])
    return await _channel_for(user)


@review_router.get("")
async def review_queue(status: Literal["pending", "verified", "changes_requested", "revoked"] = "pending", admin=Depends(get_admin)):
    return await db.channels.find({"verification_status":status},{"_id":0}).sort("verification_submitted_at",-1).limit(100).to_list(100)


@review_router.post("/{channel_id}/review")
async def review_creator(channel_id: str, body: CreatorReviewIn, admin=Depends(get_admin)):
    ch = await db.channels.find_one({"id":channel_id},{"_id":0})
    if not ch:
        raise HTTPException(404,"Channel not found")
    if ch["owner_id"] == admin["id"]:
        raise HTTPException(403,"Another administrator must review your own channel")
    if body.revision != ch.get("creator_revision",0) or (ch.get("verification_status") != ("verified" if body.decision == "revoked" else "pending")):
        raise HTTPException(409,"Verification state changed; reload")
    if not body.reason.strip():
        raise HTTPException(422,"Enter a review reason")
    await _update_creator(ch,{"verification_status":body.decision,"verification_reason":body.reason.strip(),"verification_reviewed_at":now_iso()})
    await audit("creator_verification_reviewed",admin,target=channel_id,details={"decision":body.decision,"reason":body.reason.strip()})
    return {"ok":True}


@router.get("/dashboard")
async def dashboard(user=Depends(get_user)):
    ch = await _channel_for(user)
    videos = await db.content.find({"channel_id": ch["id"]}, {"_id": 0, "subtitles_vtt": 0, "transcript": 0}).to_list(500)
    ids = [v["id"] for v in videos]
    total_views = sum(v.get("views", 0) for v in videos)

    # Real 14-day view chart from watch sessions on this channel's titles.
    days = [(now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(13, -1, -1)]
    counts = {d: 0 for d in days}
    if ids:
        async for s in db.watch_sessions.find({"content_id": {"$in": ids}, "day": {"$gte": days[0]}}, {"day": 1}):
            if s["day"] in counts:
                counts[s["day"]] += 1
    chart = [{"day": now().strptime(d, "%Y-%m-%d").strftime("%b %d"), "views": counts[d]} for d in days]

    return {
        "channel": ch, "videos": videos, "chart": chart,
        "stats": {
            "subscribers": ch.get("subscribers", 0), "total_views": total_views,
            "videos_count": len(videos),
            "revenue_usd": round(total_views * 0.005, 2),  # simulated ad share
            "lono_earned": round(total_views * 0.05, 2),
        },
    }


@router.post("/upload")
async def upload(body: ContentCreate, user=Depends(get_user)):
    ch = await _channel_for(user)
    doc = {**body.model_dump(), "id": uid(), "channel_id": ch["id"], "views": 0, "likes": 0,
           "rating": None, "year": now().year, "created_at": now_iso()}
    await db.content.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/content/{content_id}")
async def delete(content_id: str, user=Depends(get_user)):
    ch = await _channel_for(user)
    if await db.content.find_one({"id":content_id,"channel_id":ch["id"],"editorial_id":{"$exists":True}},{"id":1}):
        raise HTTPException(409,"Suspend this title in the editorial workspace to retain its history")
    res = await db.content.delete_one({"id": content_id, "channel_id": ch["id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Title not found on your channel")
    return {"ok": True}
