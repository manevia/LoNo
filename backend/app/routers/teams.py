"""Channel-scoped collaboration. Membership never changes the platform role or owner."""
from datetime import timedelta
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from ..audit import audit
from ..db import db
from ..security import get_user
from ..util import now, now_iso, uid
from .creator import _channel_for, _update_creator
from .stations import ProgrammeIn, add_programme_to_station

router = APIRouter(prefix="/creator/teams", tags=["channel teams"])
Role = Literal["administrator", "producer", "presenter", "editor"]
PERMISSIONS = {
    "owner": ["team.manage", "channel.edit", "draft.write", "draft.review", "schedule.write", "presenter.request"],
    "administrator": ["channel.edit", "draft.write", "draft.review", "schedule.write", "presenter.request"],
    "producer": ["schedule.write", "presenter.request"],
    "presenter": ["presenter.request"],
    "editor": ["draft.write"],
}


async def access(channel_id, user, permission=None):
    ch = await db.channels.find_one({"id": channel_id}, {"_id": 0, "id": 1, "owner_id": 1, "name": 1, "handle": 1})
    if not ch or not await db.users.find_one({"id": ch["owner_id"], "suspended": {"$ne": True}}, {"id": 1}):
        raise HTTPException(404, "Channel workspace not found")
    role = "owner" if ch["owner_id"] == user["id"] else None
    if not role:
        member = await db.channel_members.find_one({"channel_id": channel_id, "user_id": user["id"], "state": "active"})
        role = (member or {}).get("role")
    if role not in PERMISSIONS:
        raise HTTPException(404, "Channel workspace not found")
    if permission and permission not in PERMISSIONS[role]:
        raise HTTPException(403, "Your channel role does not allow this action")
    return ch, role


class TeamBrandIn(BaseModel):
    bio: str = Field(max_length=1500)


@router.get("/{channel_id}/branding")
async def branding(channel_id:str,user=Depends(get_user)):
    await access(channel_id,user,"channel.edit")
    return await db.channels.find_one({"id":channel_id},{"_id":0,"name":1,"bio":1})


@router.put("/{channel_id}/branding")
async def save_branding(channel_id:str,body:TeamBrandIn,user=Depends(get_user)):
    await access(channel_id,user,"channel.edit")
    ch=await db.channels.find_one({"id":channel_id},{"_id":0})
    await _update_creator(ch,{"bio":body.bio.strip()})
    await audit("channel_team_description_updated",user,target=channel_id)
    return {"ok":True}


@router.get("/{channel_id}/stations")
async def team_stations(channel_id:str,user=Depends(get_user)):
    await access(channel_id,user,"schedule.write")
    return await db.stations.find({"channel_id":channel_id,"hidden":{"$ne":True}},{"_id":0,"id":1,"name":1,"kind":1}).to_list(2)


@router.post("/{channel_id}/stations/{station_id}/programmes")
async def team_schedule(channel_id:str,station_id:str,body:ProgrammeIn,user=Depends(get_user)):
    ch,_=await access(channel_id,user,"schedule.write")
    if user.get("broadcast_blocked") or not await db.users.find_one({"id":ch["owner_id"],"broadcast_blocked":{"$ne":True}},{"id":1}):
        raise HTTPException(403,"Broadcasting restricted")
    s=await db.stations.find_one({"id":station_id,"channel_id":channel_id,"owner_id":ch["owner_id"],"hidden":{"$ne":True}},{"_id":0})
    if not s:raise HTTPException(404,"Station not found")
    # Delegation covers public programme listings only, not media access or live ingest.
    if body.format!="live" or body.file_id or body.playlist:
        raise HTTPException(422,"Team scheduling currently supports planned live programmes only")
    return await add_programme_to_station(s,body,user)


class InviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: Role


class RoleIn(BaseModel):
    role: Role


@router.get("")
async def workspaces(user=Depends(get_user)):
    own = await _channel_for(user)
    result = [{"id":own["id"], "name":own["name"], "role":"owner", "permissions":PERMISSIONS["owner"]}]
    pending = []
    rows = await db.channel_members.find({"user_id": user["id"], "state":{"$in":["active","invited"]}}, {"_id":0}).limit(100).to_list(100)
    for m in rows:
        ch = await db.channels.find_one({"id":m["channel_id"]},{"_id":0,"id":1,"name":1,"owner_id":1})
        if not ch or not await db.users.find_one({"id":ch["owner_id"],"suspended":{"$ne":True}},{"id":1}):
            continue
        item = {"id":ch["id"],"name":ch["name"],"role":m["role"],"membership_id":m["id"]}
        if m["state"]=="active":
            result.append({**item,"permissions":PERMISSIONS[m["role"]]})
        elif m["expires_at"]>now_iso():
            pending.append({**item,"expires_at":m["expires_at"]})
    return {"workspaces":result,"invitations":pending}


@router.get("/{channel_id}/members")
async def members(channel_id:str,user=Depends(get_user)):
    await access(channel_id,user,"team.manage")
    rows=await db.channel_members.find({"channel_id":channel_id,"state":{"$ne":"revoked"}},{"_id":0}).limit(100).to_list(100)
    for m in rows:
        account=await db.users.find_one({"id":m["user_id"]},{"_id":0,"name":1,"email":1})
        m["account"]=account or {"name":"Deleted account"}
    return rows


@router.post("/{channel_id}/invite")
async def invite(channel_id:str,body:InviteIn,user=Depends(get_user)):
    ch,_=await access(channel_id,user,"team.manage")
    # Bind the invitation to an existing account ID, not a claimed email at acceptance.
    target=await db.users.find_one({"email":body.email.strip().lower(),"suspended":{"$ne":True}},{"_id":0,"id":1})
    if not target or target["id"]==ch["owner_id"]:
        raise HTTPException(422,"Choose another existing LoNo account")
    mid=str(uuid5(NAMESPACE_URL,f"lono:membership:{channel_id}:{target['id']}"))
    old=await db.channel_members.find_one({"id":mid})
    if old and old["state"]=="active":
        raise HTTPException(409,"Account is already a member; change its role instead")
    if await db.channel_members.count_documents({"channel_id":channel_id,"state":{"$in":["invited","active"]}})>=100 and (not old or old["state"]=="revoked"):
        raise HTTPException(409,"Channel team limit reached")
    fields={"id":mid,"channel_id":channel_id,"user_id":target["id"],"role":body.role,"state":"invited","invited_at":now_iso(),"expires_at":(now()+timedelta(days=7)).isoformat()}
    try:
        await db.channel_members.update_one({"_id":mid,"state":{"$ne":"active"}},{"$set":fields},upsert=True)
    except DuplicateKeyError:
        raise HTTPException(409,"Membership changed; reload")
    await audit("channel_member_invited",user,target=channel_id,details={"member_id":mid,"role":body.role})
    return {"id":mid,"state":"invited"}


@router.post("/invitations/{membership_id}/accept")
async def accept(membership_id:str,body:RoleIn,user=Depends(get_user)):
    m=await db.channel_members.find_one({"id":membership_id,"user_id":user["id"],"role":body.role,"state":"invited","expires_at":{"$gt":now_iso()}})
    if not m:
        raise HTTPException(404,"Invitation unavailable or expired")
    ch=await db.channels.find_one({"id":m["channel_id"]},{"owner_id":1})
    if not ch or not await db.users.find_one({"id":ch["owner_id"],"suspended":{"$ne":True}},{"id":1}):
        raise HTTPException(404,"Channel unavailable")
    res=await db.channel_members.update_one({"id":membership_id,"user_id":user["id"],"role":body.role,"state":"invited","expires_at":{"$gt":now_iso()}},{"$set":{"state":"active","accepted_at":now_iso()}})
    if not res.matched_count: raise HTTPException(409,"Invitation changed")
    await audit("channel_member_accepted",user,target=m["channel_id"],details={"member_id":membership_id})
    return {"ok":True}


@router.put("/{channel_id}/members/{membership_id}/role")
async def change_role(channel_id:str,membership_id:str,body:RoleIn,user=Depends(get_user)):
    await access(channel_id,user,"team.manage")
    res=await db.channel_members.update_one({"id":membership_id,"channel_id":channel_id,"state":"active"},{"$set":{"role":body.role,"updated_at":now_iso()}})
    if not res.matched_count: raise HTTPException(404,"Active membership not found")
    await audit("channel_member_role_changed",user,target=channel_id,details={"member_id":membership_id,"role":body.role})
    return {"ok":True}


@router.post("/{channel_id}/members/{membership_id}/revoke")
async def revoke(channel_id:str,membership_id:str,user=Depends(get_user)):
    await access(channel_id,user,"team.manage")
    res=await db.channel_members.update_one({"id":membership_id,"channel_id":channel_id,"state":{"$in":["active","invited"]}},{"$set":{"state":"revoked","revoked_at":now_iso()}})
    if not res.matched_count: raise HTTPException(404,"Membership not found")
    await audit("channel_member_revoked",user,target=channel_id,details={"member_id":membership_id})
    return {"ok":True}


class WorkIn(BaseModel):
    kind: Literal["draft","programme","presenter"]
    title: str = Field(min_length=2,max_length=140)
    notes: str = Field(default="",max_length=2000)


WORK_PERMISSIONS={"draft":"draft.write","programme":"schedule.write","presenter":"presenter.request"}


@router.get("/{channel_id}/work")
async def work(channel_id:str,user=Depends(get_user)):
    _,role=await access(channel_id,user)
    q={"channel_id":channel_id}
    if role not in ("owner","administrator"):
        q["kind"]={"$in":[k for k,p in WORK_PERMISSIONS.items() if p in PERMISSIONS[role]]}
        q["author_id"]=user["id"]
    return await db.channel_work.find(q,{"_id":0}).sort("created_at",-1).limit(100).to_list(100)


@router.post("/{channel_id}/work")
async def create_work(channel_id:str,body:WorkIn,user=Depends(get_user)):
    await access(channel_id,user,WORK_PERMISSIONS[body.kind])
    if len(body.title.strip())<2: raise HTTPException(422,"Enter a title")
    doc={**body.model_dump(),"id":uid(),"channel_id":channel_id,"author_id":user["id"],"state":"submitted","created_at":now_iso(),"revision":0}
    await db.channel_work.insert_one(dict(doc))
    await audit("channel_work_submitted",user,target=channel_id,details={"work_id":doc["id"],"kind":body.kind})
    return doc


class WorkReview(BaseModel):
    decision: Literal["approved","changes_requested"]
    feedback: str = Field(min_length=3,max_length=500)
    revision: int = Field(ge=0)


@router.post("/{channel_id}/work/{work_id}/review")
async def review_work(channel_id:str,work_id:str,body:WorkReview,user=Depends(get_user)):
    await access(channel_id,user,"draft.review")
    res=await db.channel_work.update_one({"id":work_id,"channel_id":channel_id,"revision":body.revision,"state":"submitted"},{"$set":{"state":body.decision,"feedback":body.feedback,"reviewed_at":now_iso()},"$inc":{"revision":1}})
    if not res.matched_count: raise HTTPException(409,"Item changed or not found")
    await audit("channel_work_reviewed",user,target=channel_id,details={"work_id":work_id,"decision":body.decision})
    return {"ok":True}
