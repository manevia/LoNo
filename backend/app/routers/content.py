import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from typing import Literal

from ..db import db
from ..security import get_user, get_user_optional
from ..util import now
from .audio import CARD as AUDIO_CARD, AVAILABLE as AUDIO_AVAILABLE

router = APIRouter(tags=["content"])
P = {"_id": 0, "subtitles_vtt": 0, "transcript": 0}
EPISODE_CARD={"_id":0,"id":1,"title":1,"category":1,"thumbnail_url":1,"description":1,"duration_sec":1,"kind":1,"series":1}


@router.get("/series")
async def series_catalogue(offset:int=0):
    # Legacy standalone series remain visible; structured episodes collapse into one card per channel-owned series.
    rows=await db.content.aggregate([
        {"$match":{"kind":"series"}},
        {"$sort":{"series.season":1,"series.episode":1,"id":1}},
        {"$group":{"_id":{"$ifNull":["$series.key","$id"]},"first":{"$first":"$$ROOT"},"episodes":{"$sum":1},"seasons":{"$addToSet":"$series.season"},"updated":{"$max":"$created_at"}}},
        {"$sort":{"updated":-1,"_id":1}},{"$skip":max(0,offset)},{"$limit":101},
        {"$project":{"_id":0,"key":"$_id","id":"$first.id","title":{"$ifNull":["$first.series.series_title","$first.title"]},"category":"$first.category","thumbnail_url":"$first.thumbnail_url","kind":"$first.kind","series":"$first.series","episodes":1,"seasons":1}}
    ]).to_list(101)
    return {"items":rows[:100],"has_more":len(rows)>100}


@router.get("/series/{key}")
async def series_episodes(key:str,season:int|None=None,offset:int=0):
    q={"kind":"series","series.key":key,"gated":{"$ne":True}}
    seasons=sorted(await db.content.distinct("series.season",q))
    if not seasons:raise HTTPException(404,"Series not found")
    season=season if season is not None else seasons[0]
    rows=await db.content.find({**q,"series.season":season},EPISODE_CARD).sort([("series.episode",1),("id",1)]).skip(max(0,offset)).limit(101).to_list(101)
    return {"seasons":seasons,"season":season,"items":rows[:100],"has_more":len(rows)>100}


@router.get("/films")
async def films(format:Literal["all","feature","documentary","short_film"]="all", genre:str="", collection:str="", sort:Literal["newest","popular","rating"]="newest", offset:int=0):
    q={"kind":"movie"}
    if format=="feature":q["$or"]=[{"film.format":"feature"},{"film.format":{"$exists":False}}]
    elif format!="all":q["film.format"]=format
    if genre:q["$and"]=[{"$or":[{"film.genres":genre},{"category":genre}]}]
    if collection:q["film.collection"]=collection
    field={"newest":"created_at","popular":"views","rating":"rating"}[sort]
    rows=await db.content.find(q,P).sort([(field,-1),("id",1)]).skip(max(0,offset)).limit(100).to_list(100)
    for row in rows:
        if row.get("gated"):
            row.pop("stream_url",None)
            row.pop("media_prefix",None)
    # Facets derive solely from published movie rows, including legacy movies.
    sample=await db.content.find({"kind":"movie"},{"_id":0,"category":1,"film":1}).limit(1000).to_list(1000)
    genres=sorted({g for c in sample for g in ((c.get("film") or {}).get("genres") or [c.get("category")]) if g})
    collections=sorted({(c.get("film") or {}).get("collection") for c in sample if (c.get("film") or {}).get("collection")})
    return {"items":rows,"genres":genres,"collections":collections,"has_more":len(rows)==100}


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

    by_views = sorted(items, key=lambda c: c.get("views", 0), reverse=True)
    recent=await db.watch_sessions.aggregate([{"$match":{"started_at":{"$gte":(now()-timedelta(days=7)).isoformat()}}},{"$group":{"_id":"$content_id","starts":{"$sum":1}}},{"$sort":{"starts":-1,"_id":1}},{"$limit":40}]).to_list(40)
    trending=[by_id[r["_id"]] for r in recent if r["_id"] in by_id and not by_id[r["_id"]].get("gated")][:12]
    rails = [
        {"key": "featured", "title": "Featured today", "items": pick(lambda c: c.get("is_original"), 8)},
        {"key": "trending", "title": "Popular this week · watch starts", "items": trending},
        {"key": "top10", "title": "Most viewed titles", "items": by_views[:10]},
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
    if c.get("gated"):          # replay behind a pass: play it from My passes
        c.pop("stream_url", None); c.pop("media_prefix", None)
        offer = await db.campaigns.find_one({"replay_content_id": content_id, "status": {"$in": ["open", "paused", "closed"]}}, {"id": 1})
        c["offer_id"] = (offer or {}).get("id")
    if c.get("series") and c["series"].get("key") and not c.get("gated"):
        s=c["series"];q={"kind":"series","series.key":s["key"],"gated":{"$ne":True}}
        c["next_episode"]=await db.content.find_one({**q,"$or":[{"series.season":{"$gt":s["season"]}},{"series.season":s["season"],"series.episode":{"$gt":s["episode"]}}]},EPISODE_CARD,sort=[("series.season",1),("series.episode",1)])
        c["previous_episode"]=await db.content.find_one({**q,"$or":[{"series.season":{"$lt":s["season"]}},{"series.season":s["season"],"series.episode":{"$lt":s["episode"]}}]},EPISODE_CARD,sort=[("series.season",-1),("series.episode",-1)])
    if c.get("kind") in ("music","podcast") and (c.get("audio") or {}).get("collection_key") and not c.get("gated"):
        a=c["audio"];q={**AUDIO_AVAILABLE,"audio.collection_key":a["collection_key"]}
        c["next_audio"]=await db.content.find_one({**q,"$or":[{"audio.season":{"$gt":a["season"]}},{"audio.season":a["season"],"audio.track":{"$gt":a["track"]}}]},AUDIO_CARD,sort=[("audio.season",1),("audio.track",1)])
        c["previous_audio"]=await db.content.find_one({**q,"$or":[{"audio.season":{"$lt":a["season"]}},{"audio.season":a["season"],"audio.track":{"$lt":a["track"]}}]},AUDIO_CARD,sort=[("audio.season",-1),("audio.track",-1)])
    c["has_subtitles"] = bool(await db.content.count_documents({"id": content_id, "subtitles_vtt": {"$exists": True}}))
    c["channel"] = await db.channels.find_one({"id": c.get("channel_id")}, {"_id": 0, "creator_profile":0,"verification_reason":0,"creator_revision":0,"verification_submitted_at":0,"verification_reviewed_at":0}) if c.get("channel_id") else None
    c["similar"] = await db.content.find(
        {"category": c["category"], "id": {"$ne": content_id}}, P).limit(8).to_list(8)
    if len(c["similar"]) < 4:
        more = await db.content.find({"kind": c["kind"], "id": {"$ne": content_id}}, P).limit(8).to_list(8)
        ids = {s["id"] for s in c["similar"]}
        c["similar"] += [m for m in more if m["id"] not in ids][: 8 - len(c["similar"])]
    course = await db.courses.find_one({"content_id": content_id}, {"_id": 0, "id": 1})
    c["course_id"] = course["id"] if course else None
    if user:
        last = next((h for h in user.get("watch_history", []) if h["content_id"] == content_id), None)
        c["viewer"] = {
            "position_sec": (last or {}).get("seconds", 0),
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


@router.get("/me/history")
async def history(user=Depends(get_user)):
    """Recently watched titles, newest first, one row per title, with progress."""
    seen, rows = set(), []
    for h in user.get("watch_history", []):
        if h["content_id"] not in seen:
            seen.add(h["content_id"])
            rows.append(h)
    items = {c["id"]: c for c in await db.content.find({"id": {"$in": [r["content_id"] for r in rows]}}, P).to_list(200)}
    out = []
    for r in rows:
        c = items.get(r["content_id"])
        if not c:
            continue  # title was removed
        dur = c.get("duration_sec") or 0
        pos = r.get("seconds", 0)
        out.append({"content": c, "position_sec": pos, "watched_at": r["at"],
                    "percent": min(100, round(100 * pos / dur)) if dur else None})
    return out


@router.delete("/me/history")
async def clear_history(user=Depends(get_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"watch_history": []}})
    return {"ok": True}


@router.get("/channels")
async def list_channels():
    return await db.channels.find({}, {"_id": 0, "creator_profile":0,"verification_reason":0,"creator_revision":0,"verification_submitted_at":0,"verification_reviewed_at":0}).to_list(200)


@router.get("/channels/{channel_id}")
async def get_channel(channel_id: str, user=Depends(get_user_optional)):
    ch = await db.channels.find_one({"id": channel_id}, {"_id": 0, "creator_profile":0,"verification_reason":0,"creator_revision":0,"verification_submitted_at":0,"verification_reviewed_at":0})
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
