import random
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..db import db
from ..security import get_user, get_user_optional

router = APIRouter(tags=["content"])
P = {"_id": 0, "subtitles_vtt": 0, "transcript": 0}


@router.get("/content")
async def list_content(kind: str | None = None, category: str | None = None, limit: int = 50):
    q = {}
    if kind:
        q["kind"] = kind
    if category:
        q["category"] = category
    limit = max(1, min(limit, 200))
    return await db.content.find(q, P).limit(limit).to_list(limit)


@router.get("/content/rails")
async def home_rails(user=Depends(get_user_optional)):
    items = await db.content.find({}, P).to_list(1000)
    by_id = {c["id"]: c for c in items}

    def pick(pred, n=12):
        return [c for c in items if pred(c)][:n]

    rng = random.Random(len(items))  # stable "trending" per catalogue
    by_views = sorted(items, key=lambda c: c.get("views", 0), reverse=True)
    rails = [
        {"key": "featured", "title": "Featured today", "items": pick(lambda c: c.get("is_original"), 8)},
        {"key": "trending", "title": "Trending now", "items": rng.sample(items, min(12, len(items)))},
        {"key": "top10", "title": "Top 10 this week", "items": by_views[:10]},
        {"key": "originals", "title": "LoNo Originals", "items": pick(lambda c: c.get("is_original"))},
        {"key": "new", "title": "New releases",
         "items": sorted(items, key=lambda c: c.get("created_at", ""), reverse=True)[:12]},
        {"key": "learn", "title": "Learn and earn", "items": pick(lambda c: c.get("kind") == "course")},
        {"key": "movies", "title": "Movies", "items": pick(lambda c: c.get("kind") == "movie")},
        {"key": "series", "title": "Series", "items": pick(lambda c: c.get("kind") == "series")},
        {"key": "podcasts", "title": "Podcasts", "items": pick(lambda c: c.get("kind") == "podcast")},
        {"key": "music", "title": "Music", "items": pick(lambda c: c.get("kind") == "music")},
    ]
    if user:
        mine = [by_id[i] for i in user.get("my_list", []) if i in by_id]
        if mine:
            rails.insert(0, {"key": "mylist", "title": "My list", "items": mine[:12]})
        seen, cw = set(), []
        for h in user.get("watch_history", []):
            cid = h["content_id"]
            if cid in by_id and cid not in seen:
                seen.add(cid)
                cw.append(by_id[cid])
        if cw:
            rails.insert(0, {"key": "continue", "title": "Continue watching", "items": cw[:12]})
    return [r for r in rails if r["items"]]


@router.get("/content/{content_id}")
async def get_content(content_id: str, user=Depends(get_user_optional)):
    c = await db.content.find_one({"id": content_id}, {"_id": 0, "subtitles_vtt": 0})
    if not c:
        raise HTTPException(404, "This title doesn't exist or was removed")
    c["has_subtitles"] = bool(await db.content.count_documents({"id": content_id, "subtitles_vtt": {"$exists": True}}))
    c["channel"] = await db.channels.find_one({"id": c.get("channel_id")}, {"_id": 0}) if c.get("channel_id") else None
    c["similar"] = await db.content.find(
        {"category": c["category"], "id": {"$ne": content_id}}, P).limit(8).to_list(8)
    if len(c["similar"]) < 4:
        more = await db.content.find({"kind": c["kind"], "id": {"$ne": content_id}}, P).limit(8).to_list(8)
        ids = {s["id"] for s in c["similar"]}
        c["similar"] += [m for m in more if m["id"] not in ids][: 8 - len(c["similar"])]
    course = await db.courses.find_one({"content_id": content_id}, {"_id": 0, "id": 1})
    c["course_id"] = course["id"] if course else None
    if user:
        c["viewer"] = {
            "liked": content_id in user.get("liked", []),
            "in_list": content_id in user.get("my_list", []),
            "subscribed": c.get("channel_id") in user.get("subscribed_channels", []),
        }
    return c


@router.get("/content/{content_id}/subtitles.vtt")
async def subtitles(content_id: str):
    c = await db.content.find_one({"id": content_id}, {"subtitles_vtt": 1})
    if not c or not c.get("subtitles_vtt"):
        raise HTTPException(404, "No captions for this title yet")
    return Response(c["subtitles_vtt"], media_type="text/vtt", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/live/channels")
async def live_channels():
    tv = await db.content.find({"kind": "live_tv"}, P).to_list(50)
    radio = await db.content.find({"kind": "live_radio"}, P).to_list(50)
    return {"tv": tv, "radio": radio}


@router.get("/search")
async def search(q: str = ""):
    q = q.strip()
    if not q:
        return []
    rx = {"$regex": re.escape(q), "$options": "i"}
    return await db.content.find(
        {"$or": [{"title": rx}, {"description": rx}, {"category": rx}]}, P).limit(40).to_list(40)


# ---------- social: likes, my list, subscriptions ----------
async def _toggle(user_id: str, field: str, value: str, currently: bool):
    op = "$pull" if currently else "$addToSet"
    await db.users.update_one({"id": user_id}, {op: {field: value}})
    return not currently


@router.post("/content/{content_id}/like")
async def like(content_id: str, user=Depends(get_user)):
    if not await db.content.find_one({"id": content_id}, {"_id": 1}):
        raise HTTPException(404, "Title not found")
    liked = await _toggle(user["id"], "liked", content_id, content_id in user.get("liked", []))
    await db.content.update_one({"id": content_id}, {"$inc": {"likes": 1 if liked else -1}})
    c = await db.content.find_one({"id": content_id}, {"likes": 1})
    return {"liked": liked, "likes": c.get("likes", 0)}


@router.post("/content/{content_id}/list")
async def toggle_list(content_id: str, user=Depends(get_user)):
    if not await db.content.find_one({"id": content_id}, {"_id": 1}):
        raise HTTPException(404, "Title not found")
    return {"in_list": await _toggle(user["id"], "my_list", content_id, content_id in user.get("my_list", []))}


@router.get("/me/list")
async def my_list(user=Depends(get_user)):
    ids = user.get("my_list", [])
    items = await db.content.find({"id": {"$in": ids}}, P).to_list(200)
    order = {i: n for n, i in enumerate(ids)}
    return sorted(items, key=lambda c: order.get(c["id"], 0))


@router.get("/channels")
async def list_channels():
    return await db.channels.find({}, {"_id": 0}).to_list(200)


@router.get("/channels/{channel_id}")
async def get_channel(channel_id: str, user=Depends(get_user_optional)):
    ch = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not ch:
        raise HTTPException(404, "Channel not found")
    ch["content"] = await db.content.find({"channel_id": channel_id}, P).to_list(200)
    ch["subscribed"] = bool(user and channel_id in user.get("subscribed_channels", []))
    return ch


@router.post("/channels/{channel_id}/subscribe")
async def subscribe(channel_id: str, user=Depends(get_user)):
    ch = await db.channels.find_one({"id": channel_id}, {"_id": 0, "owner_id": 1})
    if not ch:
        raise HTTPException(404, "Channel not found")
    if ch.get("owner_id") == user["id"]:
        raise HTTPException(400, "You can't subscribe to your own channel")
    sub = await _toggle(user["id"], "subscribed_channels", channel_id,
                        channel_id in user.get("subscribed_channels", []))
    await db.channels.update_one({"id": channel_id}, {"$inc": {"subscribers": 1 if sub else -1}})
    ch = await db.channels.find_one({"id": channel_id}, {"subscribers": 1})
    return {"subscribed": sub, "subscribers": ch.get("subscribers", 0)}
