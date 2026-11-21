"""Public audio catalogue and private listener playlists."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import db
from ..security import get_user
from ..util import uid, now_iso

router=APIRouter(prefix="/audio",tags=["audio"])
CARD={"_id":0,"id":1,"kind":1,"title":1,"description":1,"category":1,"thumbnail_url":1,"duration_sec":1,"audio":1}
AVAILABLE={"kind":{"$in":["music","podcast"]},"gated":{"$ne":True}}


@router.get("/catalogue")
async def catalogue(kind:Literal["music","podcast"]="music",offset:int=0):
    rows=await db.content.aggregate([
        {"$match":{**AVAILABLE,"kind":kind}},
        {"$sort":{"audio.season":1,"audio.track":1,"id":1}},
        {"$group":{"_id":{"$ifNull":["$audio.collection_key","$id"]},"first":{"$first":"$$ROOT"},"count":{"$sum":1},"updated":{"$max":"$created_at"}}},
        {"$sort":{"updated":-1,"_id":1}},{"$skip":max(0,offset)},{"$limit":101},
        {"$project":{"_id":0,"key":"$_id","id":"$first.id","title":{"$cond":[{"$ifNull":["$first.audio.collection_key",False]},"$first.audio.collection_title","$first.title"]},"kind":"$first.kind","category":"$first.category","thumbnail_url":"$first.thumbnail_url","audio":"$first.audio","count":1}}
    ]).to_list(101)
    return {"items":rows[:100],"has_more":len(rows)>100}


@router.get("/collection/{key}")
async def collection(key:str,season:int|None=None,offset:int=0):
    q={**AVAILABLE,"audio.collection_key":key}
    seasons=sorted(await db.content.distinct("audio.season",q))
    if not seasons:raise HTTPException(404,"Audio collection not found")
    season=season if season is not None else seasons[0]
    rows=await db.content.find({**q,"audio.season":season},CARD).sort([("audio.track",1),("id",1)]).skip(max(0,offset)).limit(101).to_list(101)
    return {"items":rows[:100],"seasons":seasons,"season":season,"has_more":len(rows)>100}


@router.get("/artist/{key}")
async def artist(key:str,offset:int=0):
    q={**AVAILABLE,"audio.artist_key":key}
    profile=await db.content.find_one(q,CARD,sort=[("created_at",-1),("id",1)])
    if not profile:raise HTTPException(404,"Artist or host not found")
    rows=await db.content.find(q,CARD).sort([("created_at",-1),("id",1)]).skip(max(0,offset)).limit(101).to_list(101)
    return {"name":profile["audio"]["artist"],"bio":profile["audio"].get("artist_bio",""),"artwork":profile.get("thumbnail_url",""),"items":rows[:100],"has_more":len(rows)>100}


class PlaylistIn(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    items:list[str]=Field(default_factory=list,max_length=100)
    revision:int=Field(default=0,ge=0)


async def playlist_payload(row):
    ids=row.get("items",[])
    found=await db.content.find({**AVAILABLE,"id":{"$in":ids}},CARD).to_list(100)
    lookup={x["id"]:x for x in found}
    return {"id":row["id"],"name":row["name"],"revision":row["revision"],"items":[lookup[i] for i in ids if i in lookup],"unavailable":len(ids)-len(found)}


async def validate_playlist(body):
    name=body.name.strip()
    if not name:raise HTTPException(422,"Enter a playlist name")
    ids=list(dict.fromkeys(body.items))
    if any(len(i)>100 for i in ids):raise HTTPException(422,"Invalid audio item")
    if await db.content.count_documents({**AVAILABLE,"id":{"$in":ids}})!=len(ids):raise HTTPException(422,"Select published audio items only")
    return name,ids


@router.get("/playlists")
async def playlists(user=Depends(get_user)):
    rows=await db.audio_playlists.find({"user_id":user["id"]},{"_id":0}).sort("updated_at",-1).limit(100).to_list(100)
    return [await playlist_payload(r) for r in rows]


@router.post("/playlists")
async def create_playlist(body:PlaylistIn,user=Depends(get_user)):
    name,ids=await validate_playlist(body)
    if await db.audio_playlists.count_documents({"user_id":user["id"]})>=100:raise HTTPException(409,"Playlist limit reached")
    row={"id":uid(),"user_id":user["id"],"name":name,"items":ids,"revision":0,"updated_at":now_iso()}
    await db.audio_playlists.insert_one(dict(row))
    return await playlist_payload(row)


@router.put("/playlists/{pid}")
async def update_playlist(pid:str,body:PlaylistIn,user=Depends(get_user)):
    q={"id":pid,"user_id":user["id"]}
    row=await db.audio_playlists.find_one(q,{"_id":0})
    if not row:raise HTTPException(404,"Playlist not found")
    name,ids=await validate_playlist(body)
    result=await db.audio_playlists.update_one({**q,"revision":body.revision},{"$set":{"name":name,"items":ids,"updated_at":now_iso()},"$inc":{"revision":1}})
    if not result.matched_count:raise HTTPException(409,"Playlist changed; reload before saving")
    return await playlist_payload(await db.audio_playlists.find_one(q,{"_id":0}))


@router.delete("/playlists/{pid}")
async def delete_playlist(pid:str,user=Depends(get_user)):
    result=await db.audio_playlists.delete_one({"id":pid,"user_id":user["id"]})
    if not result.deleted_count:raise HTTPException(404,"Playlist not found")
    return {"ok":True}
