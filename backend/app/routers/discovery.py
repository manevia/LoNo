"""Public catalogue discovery, curated collections, and opt-in distribution."""
import re
from datetime import timedelta
from html import escape
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .. import config
from ..audit import audit
from ..db import db
from ..security import get_admin, get_user, get_user_optional
from ..util import now, now_iso, uid
from .teams import access

router=APIRouter(prefix="/discovery",tags=["discovery"])
KINDS=("movie","series","short","music","podcast","course","live_tv","live_radio")
MEDIA_KINDS=("movie","series","short","music","podcast")
PUBLIC={"kind":{"$in":list(KINDS)},"gated":{"$ne":True}}
CARD={"_id":0,"id":1,"title":1,"description":1,"category":1,"kind":1,"thumbnail_url":1,"duration_sec":1,"views":1,"rating":1,"created_at":1,"channel_id":1,"film":1,"series":1,"audio":1}
EMBED_CSP="default-src 'none'; media-src 'self'; style-src 'unsafe-inline'; frame-ancestors *; base-uri 'none'; form-action 'none'; sandbox allow-same-origin allow-popups allow-popups-to-escape-sandbox"


def match(fields,q):
    if not q:return {}
    rx={"$regex":re.escape(q),"$options":"i"}
    return {"$or":[{f:rx} for f in fields]}


def card(row,entity="content"):
    return {"entity":entity,"id":row["id"],"title":row.get("title") or row.get("name") or "Untitled","description":(row.get("description") or row.get("bio") or "")[:300],"kind":row.get("kind") or entity,"category":row.get("category") or "","thumbnail_url":row.get("thumbnail_url") or row.get("logo_url") or row.get("avatar_url") or "","views":row.get("views",0),"duration_sec":row.get("duration_sec",0),"subtitle":(row.get("audio") or {}).get("artist") or (row.get("series") or {}).get("series_title") or ""}


@router.get("/search")
async def search(q:str=Query(default="",max_length=120),kind:Literal["all","movie","series","short","music","podcast","course","live_tv","live_radio","station","channel"]="all",sort:Literal["newest","popular"]="newest",offset:int=Query(default=0,ge=0,le=10000),lite:bool=False):
    q=q.strip();limit=24 if lite else 48;results=[];more=False
    if kind not in ("station","channel","course"):
        filt={**PUBLIC,**match(("title","description","category","film.genres","film.collection","film.credits.name","series.series_title","series.season_title","audio.artist","audio.collection_title","audio.genre"),q)}
        if kind!="all":filt["kind"]=kind
        else:filt["kind"]={"$in":[x for x in KINDS if x!="course"]}
        rows=await db.content.find(filt,CARD).sort([("views" if sort=="popular" else "created_at",-1),("id",1)]).skip(offset).limit(limit+1).to_list(limit+1)
        results+= [card(r) for r in rows[:limit]];more|=len(rows)>limit
    if kind in ("all","course"):
        rows=await db.courses.find({"status":{"$ne":"draft"},**match(("title","description","category","instructor"),q)},{"_id":0,"id":1,"title":1,"description":1,"category":1,"thumbnail_url":1,"created_at":1}).sort([("created_at",-1),("id",1)]).skip(offset).limit(limit+1).to_list(limit+1)
        results+=[card(r,"course") for r in rows[:limit]];more|=len(rows)>limit
    if kind in ("all","station"):
        rows=await db.stations.find({"hidden":{"$ne":True},**match(("name","description","category"),q)},{"_id":0,"id":1,"name":1,"description":1,"kind":1,"category":1,"logo_url":1,"owner_id":1}).sort("id",1).skip(offset).limit(limit+1).to_list(limit+1)
        owners={r["owner_id"] for r in rows};active={r["id"] for r in await db.users.find({"id":{"$in":list(owners)},"suspended":{"$ne":True},"broadcast_blocked":{"$ne":True}},{"id":1}).to_list(len(owners) or 1)}
        results+=[card(r,"station") for r in rows[:limit] if r["owner_id"] in active];more|=len(rows)>limit
    if kind in ("all","channel"):
        rows=await db.channels.find(match(("name","handle","bio"),q),{"_id":0,"id":1,"name":1,"bio":1,"avatar_url":1,"owner_id":1}).sort("id",1).skip(offset).limit(limit+1).to_list(limit+1)
        owners={r["owner_id"] for r in rows};active={r["id"] for r in await db.users.find({"id":{"$in":list(owners)},"suspended":{"$ne":True}},{"id":1}).to_list(len(owners) or 1)}
        results+=[card(r,"channel") for r in rows[:limit] if r["owner_id"] in active];more|=len(rows)>limit
    if lite:
        for r in results:r["thumbnail_url"]=""
    return {"items":results,"has_more":more,"page_size":limit}


async def ordered_content(ids):
    rows=await db.content.find({**PUBLIC,"id":{"$in":ids}},CARD).to_list(len(ids) or 1)
    lookup={r["id"]:r for r in rows}
    return [card(lookup[i]) for i in ids if i in lookup]


@router.get("/highlights")
async def highlights(lite:bool=False,user=Depends(get_user_optional)):
    n=6 if lite else 12;rails=[]
    recent=await db.watch_sessions.aggregate([{"$match":{"started_at":{"$gte":(now()-timedelta(days=7)).isoformat()}}},{"$group":{"_id":"$content_id","starts":{"$sum":1}}},{"$sort":{"starts":-1,"_id":1}},{"$limit":60}]).to_list(60)
    trending=await ordered_content([r["_id"] for r in recent])
    if trending:rails.append({"key":"trending","title":"Popular this week · watch starts","items":trending[:n]})
    popular=await db.content.find(PUBLIC,CARD).sort([("views",-1),("id",1)]).limit(n).to_list(n)
    if popular:rails.append({"key":"popular","title":"Most viewed","items":[card(r) for r in popular]})
    if user:
        history=list(dict.fromkeys(h.get("content_id") for h in user.get("watch_history",[]) if h.get("content_id")))[:30]
        watched=await db.content.find({**PUBLIC,"id":{"$in":history}},{"kind":1,"category":1}).to_list(30)
        categories=list({r["category"] for r in watched if r.get("category")});kinds=list({r["kind"] for r in watched if r.get("kind")})
        if categories or kinds:
            rows=await db.content.find({**PUBLIC,"id":{"$nin":history},"$or":[{"category":{"$in":categories}},{"kind":{"$in":kinds}}]},CARD).sort([("views",-1),("id",1)]).limit(n).to_list(n)
            if rows:rails.insert(0,{"key":"recommended","title":"Recommended from your recent viewing","items":[card(r) for r in rows]})
    collections=await db.discovery_collections.find({"featured":True},{"_id":0}).sort([("updated_at",-1),("id",1)]).limit(12).to_list(12)
    for c in collections:
        items=await ordered_content(c["items"])
        if items:rails.append({"key":c["id"],"title":c["title"],"description":c.get("description",""),"items":items[:n]})
    if lite:
        for rail in rails:
            for r in rail["items"]:r["thumbnail_url"]=""
    return rails


class CollectionIn(BaseModel):
    title:str=Field(min_length=2,max_length=100)
    description:str=Field(default="",max_length=500)
    items:list[str]=Field(default_factory=list,max_length=30)
    featured:bool=False
    revision:int=Field(default=0,ge=0)


@router.get("/admin/collections")
async def admin_collections(admin=Depends(get_admin)):
    return await db.discovery_collections.find({}, {"_id":0}).sort("updated_at",-1).limit(100).to_list(100)


async def collection_data(body):
    title=body.title.strip();ids=list(dict.fromkeys(body.items))
    if len(title)<2:raise HTTPException(422,"Enter a collection title")
    if len(await ordered_content(ids))!=len(ids):raise HTTPException(422,"Select published, unrestricted content only")
    if body.featured and not ids:raise HTTPException(422,"Add published titles first")
    return {"title":title,"description":body.description.strip(),"items":ids,"featured":body.featured,"updated_at":now_iso()}


@router.post("/admin/collections")
async def create_collection(body:CollectionIn,admin=Depends(get_admin)):
    row={**await collection_data(body),"id":uid(),"revision":0}
    await db.discovery_collections.insert_one(dict(row));await audit("collection_created",admin,target=row["id"])
    return row


@router.put("/admin/collections/{cid}")
async def update_collection(cid:str,body:CollectionIn,admin=Depends(get_admin)):
    fields=await collection_data(body)
    result=await db.discovery_collections.update_one({"id":cid,"revision":body.revision},{"$set":fields,"$inc":{"revision":1}})
    if not result.matched_count:raise HTTPException(409,"Collection changed; reload before saving")
    await audit("collection_updated",admin,target=cid);return {"ok":True}


async def embed_file(row):
    src=row.get("stream_url") or ""
    if row.get("kind") not in MEDIA_KINDS or row.get("gated") or row.get("is_premium") or not re.fullmatch(r"/api/files/(?:editorial|uploads)/[A-Za-z0-9_./-]+",src) or ".." in src:return None
    f=await db.files.find_one({"storage_path":src.removeprefix("/api/files/"),"is_deleted":False,"pending":{"$ne":True},"protected":{"$ne":True}},{"_id":0,"content_type":1,"editorial_id":1,"channel_id":1,"user_id":1})
    if not f or f.get("content_type") not in ("video/mp4","video/webm","audio/mpeg","audio/mp4","audio/ogg","audio/wav","audio/webm"):return None
    ch=await db.channels.find_one({"id":row.get("channel_id")},{"owner_id":1})
    if not ch or not await db.users.find_one({"id":ch["owner_id"],"suspended":{"$ne":True}},{"id":1}):return None
    if f.get("editorial_id"):
        if f["editorial_id"]!=row.get("editorial_id") or f.get("channel_id")!=row.get("channel_id"):return None
    else:
        if ch["owner_id"]!=f.get("user_id"):return None
    return f


@router.get("/creator/{channel_id}")
async def distribution(channel_id:str,user=Depends(get_user)):
    await access(channel_id,user,"channel.edit")
    rows=await db.content.find({**PUBLIC,"channel_id":channel_id},{"_id":0,"id":1,"title":1,"kind":1,"stream_url":1,"channel_id":1,"editorial_id":1,"embeddable":1,"is_premium":1}).sort("id",1).limit(100).to_list(100)
    return [{"id":r["id"],"title":r["title"],"kind":r["kind"],"can_embed":bool(await embed_file(r)),"embeddable":bool(r.get("embeddable"))} for r in rows]


class EmbedIn(BaseModel):
    enabled:bool


@router.put("/creator/{channel_id}/{cid}")
async def set_embed(channel_id:str,cid:str,body:EmbedIn,user=Depends(get_user)):
    await access(channel_id,user,"channel.edit")
    row=await db.content.find_one({**PUBLIC,"channel_id":channel_id,"id":cid},{"_id":0})
    if not row:raise HTTPException(404,"Published title not found")
    if body.enabled and not await embed_file(row):raise HTTPException(422,"Only supported, locally uploaded public audio/video can be embedded")
    await db.content.update_one({"id":cid,"channel_id":channel_id},{"$set":{"embeddable":body.enabled}})
    await audit("content_embed_enabled" if body.enabled else "content_embed_disabled",user,target=cid)
    return {"ok":True}


@router.get("/embed/{cid}",response_class=HTMLResponse)
async def embed(cid:str):
    row=await db.content.find_one({**PUBLIC,"id":cid,"embeddable":True},{"_id":0})
    f=await embed_file(row) if row else None
    if not f:raise HTTPException(404,"This title is not available to embed")
    title=escape(row["title"]);src=escape(row["stream_url"],quote=True);tag="audio" if f["content_type"].startswith("audio/") else "video"
    watch=escape(config.PUBLIC_ORIGIN+"/watch/"+quote(cid,safe=""),quote=True)
    html=f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | LoNo</title><style>body{{margin:0;background:#080808;color:white;font:14px system-ui;padding:12px}}video,audio{{width:100%;max-height:75vh}}a{{color:#ffb000}}p{{margin:6px 0}}</style><{tag} controls playsinline preload="none" src="{src}"></{tag}><p>{title}</p><a href="{watch}" target="_blank" rel="noopener noreferrer">Watch on LoNo</a></html>'
    return HTMLResponse(html,headers={"Content-Security-Policy":EMBED_CSP,"Cache-Control":"no-store","Referrer-Policy":"no-referrer","Permissions-Policy":"camera=(), microphone=(), display-capture=(), geolocation=(), payment=()"})
