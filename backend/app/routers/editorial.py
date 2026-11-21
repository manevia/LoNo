"""Versioned private media drafts; only approved releases enter the public catalogue."""
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from .. import config
from ..audit import audit
from ..broadcast.secrets_box import sign
from ..db import db
from ..security import get_admin, get_user
from ..storage import storage
from ..util import now, now_iso, uid
from .teams import access

router=APIRouter(prefix="/creator/editorial",tags=["editorial"])
moderation=APIRouter(prefix="/admin/editorial",tags=["editorial moderation"])
MEDIA={"video/mp4":"mp4","video/webm":"webm","audio/mpeg":"mp3","audio/mp4":"m4a","audio/ogg":"ogg","audio/wav":"wav","audio/webm":"webm","image/jpeg":"jpg","image/png":"png","image/webp":"webp"}


class FilmCredit(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    role:str=Field(min_length=1,max_length=80)


class FilmIn(BaseModel):
    format:Literal["feature","documentary","short_film"]="feature"
    genres:list[str]=Field(default_factory=list,max_length=8)
    credits:list[FilmCredit]=Field(default_factory=list,max_length=30)
    release_year:int|None=Field(default=None,ge=1888,le=2100)
    runtime_minutes:int|None=Field(default=None,ge=1,le=1440)
    maturity:Literal["unrated","general","parental_guidance","13_plus","16_plus","18_plus"]="unrated"
    country:str=Field(default="",max_length=80)
    language:str=Field(default="",max_length=80)
    collection:str=Field(default="",max_length=100)
    trailer_id:str|None=None


class DraftIn(BaseModel):
    title:str=Field(min_length=2,max_length=140)
    description:str=Field(default="",max_length=4000)
    category:str=Field(min_length=1,max_length=60)
    kind:Literal["movie","series","short","music","podcast"]="short"
    media_id:str|None=None
    thumbnail_id:str|None=None
    film:FilmIn|None=None
    revision:int=Field(default=0,ge=0)


class Decision(BaseModel):
    revision:int=Field(ge=0)
    action:Literal["submit","approve","changes_requested","schedule","cancel_schedule","suspend"]
    reason:str=Field(default="",max_length=500)
    publish_at:datetime|None=None


async def _draft(channel_id,draft_id,user,permission=None):
    _,role=await access(channel_id,user,permission)
    d=await db.editorial_drafts.find_one({"id":draft_id,"channel_id":channel_id},{"_id":0})
    if not d or (role not in ("owner","administrator") and d["author_id"]!=user["id"]):
        raise HTTPException(404,"Draft not found")
    return d


def event(action,actor,reason=""):
    return {"action":action,"at":now_iso(),"actor_id":actor,"reason":reason}


async def _change(d,fields,action,actor,reason="",version=None):
    push={"history":{"$each":[event(action,actor,reason)],"$slice":-100}}
    if version is not None:push["versions"]={"$each":[version],"$slice":-50}
    res=await db.editorial_drafts.update_one({"id":d["id"],"revision":d["revision"],"status":d["status"]},{"$set":{**fields,"updated_at":now_iso()},"$inc":{"revision":1},"$push":push})
    if not res.matched_count:raise HTTPException(409,"Draft changed; reload before retrying")


async def _asset(d,aid,kind):
    if not aid:return None
    f=await db.files.find_one({"id":aid,"editorial_id":d["id"],"is_deleted":False,"pending":{"$ne":True}},{"_id":0})
    if not f or not f["content_type"].startswith(kind):raise HTTPException(422,"Select a matching private asset from this draft")
    return f


async def _metadata(d,body):
    data=body.model_dump(exclude={"revision"})
    if not data["title"].strip() or not data["category"].strip():raise HTTPException(422,"Enter a title and category")
    if data["media_id"]:
        f=await _asset(d,data["media_id"],"audio/" if body.kind in ("music","podcast") else "video/")
    if data["thumbnail_id"]:await _asset(d,data["thumbnail_id"],"image/")
    if body.film:
        if body.kind!="movie":raise HTTPException(422,"Film metadata is only for movies and documentaries")
        data["film"]["genres"]=list(dict.fromkeys(g.strip() for g in body.film.genres if g.strip()))
        if any(len(g)>60 for g in data["film"]["genres"]):raise HTTPException(422,"Genre names must be 60 characters or fewer")
        if any(not c.name.strip() or not c.role.strip() for c in body.film.credits):raise HTTPException(422,"Enter a name and role for each credit")
        if body.film.trailer_id:await _asset(d,body.film.trailer_id,"video/")
    elif body.kind=="movie":
        data["film"]=FilmIn().model_dump()
    return data


@router.get("/{channel_id}")
async def list_drafts(channel_id:str,user=Depends(get_user)):
    _,role=await access(channel_id,user,"draft.write")
    q={"channel_id":channel_id}
    if role not in ("owner","administrator"):q["author_id"]=user["id"]
    return await db.editorial_drafts.find(q,{"_id":0,"published_snapshot":0}).sort("updated_at",-1).limit(100).to_list(100)


@router.post("/{channel_id}")
async def create(channel_id:str,body:DraftIn,user=Depends(get_user)):
    await access(channel_id,user,"draft.write")
    did=uid(); stamp=now_iso()
    d={"id":did,"channel_id":channel_id,"author_id":user["id"],"status":"draft","revision":0,"created_at":stamp,"updated_at":stamp}
    data=await _metadata(d,body)
    d.update({"metadata":data,"versions":[{"number":1,"at":stamp,"metadata":data}],"history":[event("created",user["id"])]})
    await db.editorial_drafts.insert_one(dict(d));return d


@router.put("/{channel_id}/{draft_id}")
async def update(channel_id:str,draft_id:str,body:DraftIn,user=Depends(get_user)):
    d=await _draft(channel_id,draft_id,user,"draft.write")
    if d.get("moderation_hold") or d["status"] not in ("draft","changes_requested","suspended") or body.revision!=d["revision"]:raise HTTPException(409,"Draft is locked or changed")
    data=await _metadata(d,body)
    version={"number":d["versions"][-1]["number"]+1,"at":now_iso(),"metadata":data}
    await _change(d,{"metadata":data,"status":"draft","publish_at":None},"version_saved",user["id"],version=version)
    return {"ok":True}


@router.post("/{channel_id}/{draft_id}/assets")
async def upload(channel_id:str,draft_id:str,file:UploadFile=File(...),user=Depends(get_user)):
    d=await _draft(channel_id,draft_id,user,"draft.write")
    if d.get("moderation_hold") or d["status"] not in ("draft","changes_requested","suspended"):raise HTTPException(409,"Draft is locked")
    ct=file.content_type or ""
    if ct not in MEDIA:raise HTTPException(422,"Use supported MP4/WebM, audio or JPEG/PNG/WebP media")
    if await db.files.count_documents({"editorial_id":draft_id,"is_deleted":False})>=50:raise HTTPException(409,"Draft asset limit reached")
    fid=uid();key=f"editorial/{channel_id}/{draft_id}/{fid}.{MEDIA[ct]}";tmp=storage.temp_dir()/f"{fid}.part";size=0
    try:
        with open(tmp,"wb") as out:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>config.MAX_UPLOAD_MB*1024*1024:raise HTTPException(413,"File exceeds upload limit")
                await asyncio.to_thread(out.write,chunk)
        if not size:raise HTTPException(422,"Empty file")
        await storage.put_file(key,tmp,ct)
    finally:tmp.unlink(missing_ok=True)
    await db.files.insert_one({"id":fid,"user_id":user["id"],"editorial_id":draft_id,"channel_id":channel_id,"storage_path":key,"original_filename":(file.filename or "media")[:255],"content_type":ct,"size":size,"is_deleted":False,"created_at":now_iso()})
    return {"id":fid,"name":file.filename,"content_type":ct}


@router.get("/{channel_id}/{draft_id}/assets")
async def assets(channel_id:str,draft_id:str,user=Depends(get_user)):
    await _draft(channel_id,draft_id,user,"draft.write")
    rows=await db.files.find({"editorial_id":draft_id,"is_deleted":False},{"_id":0,"id":1,"original_filename":1,"content_type":1,"size":1}).to_list(50)
    return rows


@router.get("/{channel_id}/{draft_id}/assets/{asset_id}/preview")
async def preview(channel_id:str,draft_id:str,asset_id:str,user=Depends(get_user)):
    await _draft(channel_id,draft_id,user,"draft.write")
    f=await db.files.find_one({"id":asset_id,"editorial_id":draft_id,"is_deleted":False})
    if not f:raise HTTPException(404,"Asset not found")
    exp=int(time.time())+300;path=f["storage_path"]
    return {"url":f"/api/files/{path}?exp={exp}&sig={sign(path,str(exp))}"}


@router.post("/{channel_id}/{draft_id}/decision")
async def decide(channel_id:str,draft_id:str,body:Decision,user=Depends(get_user)):
    d=await _draft(channel_id,draft_id,user,"draft.write" if body.action=="submit" else "draft.review")
    if d.get("moderation_hold") or d["revision"]!=body.revision:raise HTTPException(409,"Draft is locked or changed")
    allowed={"submit":("draft","changes_requested"),"approve":("submitted",),"changes_requested":("submitted",),"schedule":("approved",),"cancel_schedule":("scheduled",),"suspend":("published",)}
    if d["status"] not in allowed[body.action]:raise HTTPException(409,"Invalid editorial transition")
    if body.action in ("changes_requested","suspend") and len(body.reason.strip())<3:raise HTTPException(422,"Enter a reason")
    if body.action=="submit" and not d["metadata"].get("media_id"):raise HTTPException(422,"Attach media before submission")
    if body.action=="schedule":
        when=body.publish_at or now()
        if when.tzinfo is None:raise HTTPException(422,"Include the time zone")
        fields={"status":"scheduled","publish_at":when.astimezone(timezone.utc).isoformat()}
    else:fields={"status":{"submit":"submitted","approve":"approved","changes_requested":"changes_requested","cancel_schedule":"approved","suspend":"unpublishing"}[body.action]}
    await _change(d,fields,body.action,user["id"],body.reason)
    await audit("editorial_"+body.action,user,target=draft_id)
    return {"ok":True}


@moderation.post("/{draft_id}/suspend")
async def moderate(draft_id:str,body:Decision,admin=Depends(get_admin)):
    d=await db.editorial_drafts.find_one({"id":draft_id},{"_id":0})
    if not d or d["status"]!="published" or d["revision"]!=body.revision:raise HTTPException(409,"Published release changed")
    if body.action!="suspend" or len(body.reason.strip())<3:raise HTTPException(422,"Enter a suspension reason")
    await _change(d,{"status":"unpublishing","moderation_hold":True},"moderator_suspend",admin["id"],body.reason)
    await audit("editorial_moderator_suspend",admin,target=draft_id)
    return {"ok":True}


@moderation.get("")
async def published(admin=Depends(get_admin)):
    return await db.editorial_drafts.find({"$or":[{"status":"published"},{"moderation_hold":True}]},{"_id":0,"id":1,"channel_id":1,"metadata.title":1,"revision":1,"published_at":1,"status":1,"moderation_hold":1}).limit(100).to_list(100)


class ReleaseHold(BaseModel):
    revision:int=Field(ge=0)
    reason:str=Field(min_length=3,max_length=500)


@moderation.post("/{draft_id}/release-hold")
async def release_hold(draft_id:str,body:ReleaseHold,admin=Depends(get_admin)):
    d=await db.editorial_drafts.find_one({"id":draft_id,"moderation_hold":True,"status":"suspended"},{"_id":0})
    if not d or d["revision"]!=body.revision:raise HTTPException(409,"Moderation state changed")
    await _change(d,{"moderation_hold":False,"status":"changes_requested"},"moderation_released",admin["id"],body.reason)
    await audit("editorial_moderation_released",admin,target=draft_id)
    return {"ok":True}


async def process_release(d):
    if d["status"]=="unpublishing":
        public=await db.content.find_one({"id":d["id"],"editorial_id":d["id"]},{"_id":0})
        if public:await db.editorial_drafts.update_one({"id":d["id"],"status":"unpublishing"},{"$set":{"published_snapshot":public}})
        await db.content.delete_one({"id":d["id"],"editorial_id":d["id"]})
        await _change(d,{"status":"suspended"},"unpublished","system")
        return
    if d["status"]=="scheduled":
        await _change(d,{"status":"publishing"},"publication_claimed","system")
        d=await db.editorial_drafts.find_one({"id":d["id"]},{"_id":0})
    ch=await db.channels.find_one({"id":d["channel_id"]},{"owner_id":1})
    if not ch or not await db.users.find_one({"id":ch["owner_id"],"suspended":{"$ne":True}},{"id":1}):
        await _change(d,{"status":"changes_requested"},"publication_blocked","system","Channel unavailable");return
    m=d["metadata"]
    try:
        f=await _asset(d,m["media_id"],"audio/" if m["kind"] in ("music","podcast") else "video/")
        image=await _asset(d,m.get("thumbnail_id"),"image/")
        trailer=await _asset(d,(m.get("film") or {}).get("trailer_id"),"video/")
        if not f or not await storage.exists(f["storage_path"]) or (image and not await storage.exists(image["storage_path"])):raise HTTPException(422,"Media missing")
        if trailer and not await storage.exists(trailer["storage_path"]):raise HTTPException(422,"Trailer missing")
    except HTTPException:
        await _change(d,{"status":"changes_requested"},"publication_blocked","system","Media missing or invalid");return
    old=d.get("published_snapshot") or {}
    content={"id":d["id"],"editorial_id":d["id"],"channel_id":d["channel_id"],"title":m["title"],"description":m["description"],"category":m["category"],"kind":m["kind"],"stream_url":"/api/files/"+f["storage_path"],"thumbnail_url":"/api/files/"+image["storage_path"] if image else "", "duration_sec":0,"views":old.get("views",0),"likes":old.get("likes",0),"rating":old.get("rating"),"year":now().year,"created_at":old.get("created_at") or now_iso()}
    if m["kind"]=="movie":
        film={**(m.get("film") or FilmIn().model_dump())};film.pop("trailer_id",None)
        content["film"]=film
        if trailer:content["trailer_url"]="/api/files/"+trailer["storage_path"]
        if film.get("release_year"):content["year"]=film["release_year"]
        if film.get("runtime_minutes"):content["duration_sec"]=film["runtime_minutes"]*60
    try:await db.content.update_one({"id":d["id"],"editorial_id":d["id"]},{"$setOnInsert":content},upsert=True)
    except DuplicateKeyError:raise HTTPException(409,"Publication ID conflict")
    await _change(d,{"status":"published","published_at":now_iso()},"published","system")


async def publication_loop(stop):
    while not stop.is_set():
        try:
            rows=await db.editorial_drafts.find({"$or":[{"status":"scheduled","publish_at":{"$lte":now_iso()}},{"status":{"$in":["publishing","unpublishing"]}}]},{"_id":0}).limit(30).to_list(30)
            for d in rows:
                lease=uid()
                claimed=await db.editorial_drafts.update_one({"id":d["id"],"revision":d["revision"], "$or":[{"lease_until":{"$exists":False}},{"lease_until":{"$lt":now_iso()}}]},{"$set":{"lease_until":(now()+timedelta(minutes=5)).isoformat(),"lease_token":lease}})
                if not claimed.matched_count:continue
                try:await process_release(d)
                except Exception:logging.getLogger("lono").exception("Editorial release processing failed")
                finally:await db.editorial_drafts.update_one({"id":d["id"],"lease_token":lease},{"$unset":{"lease_until":"","lease_token":""}})
        except Exception:logging.getLogger("lono").exception("Editorial scheduler failed")
        try:await asyncio.wait_for(stop.wait(),10)
        except asyncio.TimeoutError:pass
