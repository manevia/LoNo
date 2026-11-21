"""Admin console API: overview, moderation queue, users, courses, audit log.

Admins are set with ADMIN_EMAILS (or role=admin in the database); there's no
endpoint that grants admin rights, so nobody can promote themselves."""
import asyncio
import csv
import os
import shutil
import io
import re
from datetime import timedelta
from typing import Literal

from fastapi import Request, APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..audit import audit
from ..db import db
from ..security import get_admin, is_admin
from ..util import now, now_iso, today

router = APIRouter(prefix="/admin", tags=["admin"])


class ResolveIn(BaseModel):
    action: Literal["hide", "dismiss"]
    note: str = Field(default="", max_length=500)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.get("/broadcasts")
async def broadcast_center(admin=Depends(get_admin)):
    from .. import config
    from ..broadcast import abr, media
    from ..broadcast.relays import manager
    from . import broadcast as bc

    active_query = {"status": {"$in": list(bc.ACTIVE)}}
    projection = {k: 1 for k in ("id", "owner_id", "title", "kind", "visibility", "status", "created_at",
                                 "started_at", "ended_at", "content_id", "last_content_id", "recording_id", "moderation_reason", "ingest_id")}
    projection["_id"] = 0
    active = await db.broadcast_sessions.find(active_query, projection).sort("created_at", -1).to_list(50)
    history = await db.broadcast_sessions.find({"status": "ended"}, projection).sort("ended_at", -1).to_list(100)
    recordings = await db.recordings.find({}, {"_id": 0, "id": 1, "owner_id": 1, "title": 1, "status": 1,
         "visibility": 1, "duration_sec": 1, "size": 1, "created_at": 1, "moderation_hold": 1}).sort("created_at", -1).to_list(100)
    ids = list({s["owner_id"] for s in active + history + recordings})
    owners = {u["id"]: u.get("name", "Member") for u in await db.users.find({"id": {"$in": ids}}, {"id": 1, "name": 1}).to_list(len(ids) or 1)}
    content_ids = [s.get("content_id") or s.get("last_content_id") for s in active + history]
    audience = {r["_id"]: r["count"] async for r in db.watch_sessions.aggregate([
        {"$match": {"content_id": {"$in": [i for i in content_ids if i]}}},
        {"$group": {"_id": "$content_id", "count": {"$sum": 1}}}])}
    sem = asyncio.Semaphore(5)

    async def health(s):
        async with sem:
            feed = await media.path_info(f"live/{s['ingest_id']}") if config.MEDIA_ENABLED else None
        relays = manager.get(s["id"])
        s["feed"] = {k: feed.get(k) for k in ("ready", "tracks", "bitrate_kbps")} if feed else None
        s["adaptive"] = bc._adaptive_status(s, relays)
        s["recorder_state"] = (relays.get("recorder") or {}).get("state")

    await asyncio.gather(*(health(s) for s in active))
    for s in active + history:
        cid = s.pop("content_id", None) or s.pop("last_content_id", None)
        s.pop("last_content_id", None)
        s.pop("ingest_id", None)
        s["watch_starts"] = audience.get(cid, 0) if cid and s.get("visibility") == "public" else None
        s["owner_name"] = owners.get(s["owner_id"], "Former member")
    for r in recordings:
        r["owner_name"] = owners.get(r["owner_id"], "Former member")
    encoders = len(bc._adaptive_running())
    limit, reason = abr.capacity(encoders) if abr.enabled() else (0, "Adaptive encoding disabled")
    try:
        disk_free_gib = round(shutil.disk_usage(config.RECORDINGS_DIR).free / 1024**3, 1)
    except OSError:
        disk_free_gib = None
    return {"active": active, "history": history, "recordings": recordings, "as_of": now_iso(),
            "live_count": await db.broadcast_sessions.count_documents({"status": "live"}),
            "open_count": await db.broadcast_sessions.count_documents(active_query),
            "resources": {"media_enabled": config.MEDIA_ENABLED, "encoders": encoders, "encoder_limit": limit,
                          "admission_reason": reason, "disk_free_gib": disk_free_gib,
                          "cpu_load_1m": round(os.getloadavg()[0], 2) if hasattr(os, "getloadavg") else None}}


@router.post("/broadcasts/{session_id}/end")
async def moderate_broadcast(session_id: str, body: ReasonIn, admin=Depends(get_admin)):
    from .broadcast import stop_session_for, ACTIVE
    s = await db.broadcast_sessions.find_one({"id": session_id, "status": {"$in": list(ACTIVE)}})
    if not s:
        raise HTTPException(404, "No open broadcast with this ID")
    reason = body.reason.strip()
    if len(reason) < 3:
        raise HTTPException(422, "Enter a moderation reason")
    await stop_session_for({"id": s["owner_id"]}, session_id)
    await db.broadcast_sessions.update_one({"id": session_id}, {"$set": {"moderation_reason": reason}})
    await audit("broadcast_moderated", admin, target=session_id, details={"reason": reason})
    return {"ok": True}


class BroadcastPermissionIn(ReasonIn):
    blocked: bool


@router.post("/users/{user_id}/broadcast-permission")
async def broadcast_permission(user_id: str, body: BroadcastPermissionIn, admin=Depends(get_admin)):
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(404, "User not found")
    if is_admin(u):
        raise HTTPException(400, "Admin broadcasting permissions cannot be changed here")
    if len(body.reason.strip()) < 3:
        raise HTTPException(422, "Enter a reason")
    if body.blocked and await db.broadcast_sessions.find_one({"owner_id": user_id, "status": {"$in": ["live", "created"]}}):
        raise HTTPException(409, "End this creator's open sessions first")
    await db.users.update_one({"id": user_id}, {"$set": {"broadcast_blocked": body.blocked}})
    await audit("broadcast_permission_changed", admin, target=user_id, details={"blocked": body.blocked, "reason": body.reason.strip()})
    return {"ok": True}


@router.post("/recordings/{recording_id}/hold")
async def hold_recording(recording_id: str, body: ReasonIn, admin=Depends(get_admin)):
    r = await db.recordings.find_one({"id": recording_id})
    if not r:
        raise HTTPException(404, "Recording not found")
    if len(body.reason.strip()) < 3:
        raise HTTPException(422, "Enter a reason")
    await db.recordings.update_one({"id": recording_id}, {"$set": {"moderation_hold": True, "visibility": "private", "publish_at": None, "content_id": None}})
    await db.content.delete_many({"recording_id": recording_id})
    await audit("recording_held", admin, target=recording_id, details={"reason": body.reason.strip()})
    return {"ok": True}


@router.post("/recordings/{recording_id}/release")
async def release_recording(recording_id: str, body: ReasonIn, admin=Depends(get_admin)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(422, "Enter a reason")
    result = await db.recordings.update_one({"id": recording_id, "moderation_hold": True}, {"$set": {"moderation_hold": False}})
    if not result.matched_count:
        raise HTTPException(404, "No held recording with this ID")
    await audit("recording_released", admin, target=recording_id, details={"reason": body.reason.strip()})
    return {"ok": True}


@router.get("/overview")
async def overview(admin=Depends(get_admin)):
    since = (now() - timedelta(days=30)).isoformat()
    active_today = len(await db.watch_sessions.distinct("user_id", {"day": today(), "user_id": {"$ne": None}}))
    return {
        "users": await db.users.count_documents({}),
        "suspended": await db.users.count_documents({"suspended": True}),
        "active_today": active_today,
        "content": await db.content.count_documents({}),
        "courses_published": await db.courses.count_documents({"status": {"$ne": "draft"}}),
        "courses_draft": await db.courses.count_documents({"status": "draft"}),
        "certificates": await db.certificates.count_documents({}),
        "open_reports": await db.reports.count_documents({"status": "open"}),
        "data_exports_30d": await db.audit_log.count_documents({"action": "data_export", "at": {"$gte": since}}),
        "deletions_30d": await db.audit_log.count_documents({"action": "account_deleted", "at": {"$gte": since}}),
    }


# ---------- moderation ----------
@router.get("/reports")
async def reports(status: Literal["open", "resolved", "all"] = "open", admin=Depends(get_admin)):
    q = {} if status == "all" else {"status": status}
    items = await db.reports.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    ids = list({r["target_id"] for r in items})
    reviews = {r["id"]: r for r in await db.reviews.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids) or 1)}
    courses = {c["id"]: c["title"] for c in await db.courses.find(
        {"id": {"$in": list({r["course_id"] for r in items})}}, {"id": 1, "title": 1}).to_list(500)}
    reporters = {u["id"]: u["name"] for u in await db.users.find(
        {"id": {"$in": list({r["reporter_id"] for r in items})}}, {"id": 1, "name": 1}).to_list(500)}
    for r in items:
        r["review"] = reviews.get(r["target_id"])
        r["course_title"] = courses.get(r["course_id"])
        r["reporter_name"] = reporters.get(r["reporter_id"], "Former member")
    return items


@router.post("/reports/{report_id}/resolve")
async def resolve(report_id: str, body: ResolveIn, admin=Depends(get_admin)):
    rep = await db.reports.find_one({"id": report_id})
    if not rep:
        raise HTTPException(404, "Report not found")
    if rep["status"] != "open":
        raise HTTPException(409, "This report was already resolved")
    if body.action == "hide":
        await db.reviews.update_one({"id": rep["target_id"]}, {"$set": {"hidden": True, "hidden_at": now_iso()}})
        course = await db.courses.find_one({"id": rep["course_id"]})
        if course:
            from .learn import _refresh_rating
            await _refresh_rating(course)
    # one decision closes every open report on the same review
    await db.reports.update_many({"target_id": rep["target_id"], "status": "open"}, {"$set": {
        "status": "resolved", "resolution": body.action, "note": body.note, "resolved_by": admin["id"],
        "resolved_at": now_iso()}})
    await audit(f"review_{'hidden' if body.action == 'hide' else 'report_dismissed'}", admin,
                target=rep["target_id"], details={"report_id": report_id, "note": body.note})
    return {"ok": True}


@router.post("/reviews/{review_id}/restore")
async def restore_review(review_id: str, admin=Depends(get_admin)):
    r = await db.reviews.find_one({"id": review_id, "hidden": True})
    if not r:
        raise HTTPException(404, "No hidden review with this id")
    await db.reviews.update_one({"id": review_id}, {"$set": {"hidden": False}})
    course = await db.courses.find_one({"id": r["course_id"]})
    if course:
        from .learn import _refresh_rating
        await _refresh_rating(course)
    await audit("review_restored", admin, target=review_id)
    return {"ok": True}


# ---------- users ----------
@router.get("/users")
async def users(q: str = "", admin=Depends(get_admin)):
    query = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query = {"$or": [{"email": rx}, {"name": rx}]}
    items = await db.users.find(query, {"_id": 0, "password_hash": 0, "watch_history": 0, "liked": 0,
                                        "my_list": 0}).sort("created_at", -1).limit(100).to_list(100)
    for u in items:
        u["is_admin"] = is_admin(u)
    return items


async def _set_suspended(user_id: str, value: bool, admin: dict, reason: str = ""):
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(404, "User not found")
    if value and is_admin(u):
        raise HTTPException(400, "Admins can't be suspended. Remove their admin role first (python -m app.admin_setup remove-admin <email>).")
    await db.users.update_one({"id": user_id}, {"$set": {"suspended": value, "suspended_reason": reason if value else None}})
    await audit("user_suspended" if value else "user_reinstated", admin, target=user_id, details={"reason": reason})
    return {"ok": True, "suspended": value}


@router.post("/users/{user_id}/suspend")
async def suspend(user_id: str, body: ReasonIn, admin=Depends(get_admin)):
    return await _set_suspended(user_id, True, admin, body.reason.strip())


@router.post("/users/{user_id}/reinstate")
async def reinstate(user_id: str, admin=Depends(get_admin)):
    return await _set_suspended(user_id, False, admin)


# ---------- courses ----------
@router.get("/courses")
async def courses(admin=Depends(get_admin)):
    items = await db.courses.find({}, {"_id": 0, "lessons": 0, "quiz": 0}).sort("created_at", -1).to_list(500)
    owners = {u["id"]: u["name"] for u in await db.users.find(
        {"id": {"$in": list({c.get("owner_id") for c in items if c.get("owner_id")})}}, {"id": 1, "name": 1}).to_list(500)}
    for c in items:
        c["status"] = c.get("status", "published")
        c["owner_name"] = owners.get(c.get("owner_id"), "LoNo" if not c.get("owner_id") else "Former member")
    return items


@router.post("/courses/{course_id}/unpublish")
async def unpublish(course_id: str, body: ReasonIn, admin=Depends(get_admin)):
    c = await db.courses.find_one({"id": course_id})
    if not c:
        raise HTTPException(404, "Course not found")
    if c.get("content_id"):
        await db.content.delete_one({"id": c["content_id"]})
    await db.courses.update_one({"id": course_id}, {"$set": {
        "status": "draft", "content_id": None, "moderation_note": body.reason.strip()}})
    await audit("course_unpublished", admin, target=course_id, details={"reason": body.reason.strip(), "title": c["title"]})
    return {"ok": True}


# ---------- audit log ----------
def _cell(v) -> str:
    """Stop spreadsheet apps treating user-supplied text (names, notes) as formulas."""
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


async def _audit_rows(action: str, days: int):
    q = {"at": {"$gte": (now() - timedelta(days=days)).isoformat()}}
    if action:
        q["action"] = action
    return await db.audit_log.find(q, {"_id": 0}).sort("at", -1).to_list(5000)


@router.get("/audit")
async def audit_log(action: str = "", days: int = 30, admin=Depends(get_admin)):
    days = max(1, min(days, 3650))
    rows = await _audit_rows(action, days)
    actions = sorted(await db.audit_log.distinct("action"))
    return {"items": rows[:500], "total": len(rows), "actions": actions}


@router.get("/audit.csv")
async def audit_csv(action: str = "", days: int = 30, admin=Depends(get_admin)):
    rows = await _audit_rows(action, max(1, min(days, 3650)))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["at", "action", "actor_id", "actor_name", "target", "subject_email_hash", "details"])
    for r in rows:
        w.writerow([_cell(x) for x in (r["at"], r["action"], r.get("actor_id"), r.get("actor_name"), r.get("target"),
                    r.get("subject_email_hash"), "; ".join(f"{k}={v}" for k, v in (r.get("details") or {}).items()))])
    await audit("audit_exported", admin, details={"rows": len(rows), "action": action, "days": days})
    return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8-sig")), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="lono-audit-{today()}.csv"'})


@router.get("/request-info")
async def request_info(request: Request, admin=Depends(get_admin)):
    """How the API sees this request behind proxies (deployment check): the client
    address should be the visitor's, and the scheme https in production."""
    return {"client_ip": request.client.host if request.client else None, "scheme": request.url.scheme,
            "host": request.headers.get("host"), "forwarded_for": request.headers.get("x-forwarded-for"),
            "forwarded_proto": request.headers.get("x-forwarded-proto")}
