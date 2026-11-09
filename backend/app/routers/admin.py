"""Admin console API: overview, moderation queue, users, courses, audit log.

Admins are set with ADMIN_EMAILS (or role=admin in the database); there's no
endpoint that grants admin rights, so nobody can promote themselves."""
import csv
import io
import re
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
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
        raise HTTPException(400, "Admins can't be suspended here. Remove them from ADMIN_EMAILS first.")
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
