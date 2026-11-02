from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import db
from ..security import get_user
from ..util import now, now_iso, uid

router = APIRouter(prefix="/creator", tags=["creator"])


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
        "id": uid(), "owner_id": user["id"], "name": f"{user['name']}'s channel",
        "handle": f"@{''.join(x for x in user['name'].lower() if x.isalnum())}_{user['id'][:4]}",
        "banner_url": "https://images.unsplash.com/photo-1655947717064-d856af599bd1?crop=entropy&cs=srgb&fm=jpg&q=85",
        "avatar_url": user["avatar_url"], "bio": "New creator on LoNo", "subscribers": 0,
        "created_at": now_iso(),
    }
    await db.channels.insert_one(ch)
    ch.pop("_id", None)
    return ch


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
    res = await db.content.delete_one({"id": content_id, "channel_id": ch["id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Title not found on your channel")
    return {"ok": True}
