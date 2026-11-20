"""Permanent stations with clock-synchronised, viewer-side scheduled playout."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError

from ..audit import audit
from ..db import db
from ..security import get_admin, get_user
from ..storage import storage
from ..util import now, now_iso, uid
from .creator import _channel_for

router = APIRouter(tags=["stations"])
Kind = Literal["live_tv", "live_radio"]
STARTER_MEDIA = {
    "6166455a-cc77-5c91-aa81-ec62d9da0b93": ("LoNo_TV_Opening_Ident.mp4", "video/mp4"),
    "ff572199-4bc6-563f-bf37-cbe0708dae96": ("LoNo_Radio_Opening_Ident.mp3", "audio/mpeg"),
}


class StationIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=1500)
    logo_url: str = Field(default="", max_length=1000)
    banner_url: str = Field(default="", max_length=1000)
    category: str = Field(default="General", min_length=1, max_length=60)

    @field_validator("name", "category")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("Enter a name or category")
        return v.strip()

    @field_validator("logo_url", "banner_url")
    @classmethod
    def image_url(cls, v):
        v = v.strip()
        if not v:
            return v
        # The server never fetches or proxies an external image URL.
        parsed = urlsplit(v)
        if v.startswith("/api/files/uploads/") and not parsed.query and not parsed.fragment and ".." not in v:
            return v
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            return v
        raise ValueError("Use an HTTPS image URL or upload an image")


class ProgrammeIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=1000)
    start: datetime
    end: datetime
    format: Literal["live", "prerecorded"] = "live"
    file_id: str | None = Field(default=None, max_length=100)


class AutomationIn(BaseModel):
    enabled: bool = False
    fallback_file_id: str | None = Field(default=None, max_length=100)


def eligible_file(f, station):
    """Only completed, unprotected first-party uploads of the station owner."""
    if not f or f.get("user_id") != station["owner_id"] or f.get("protected") or f.get("pending") or f.get("is_deleted"):
        return False
    if not f.get("storage_path", "").startswith(f"uploads/{station['owner_id']}/"):
        return False
    types = ("video/mp4", "video/webm") if station["kind"] == "live_tv" else ("audio/mpeg", "audio/mp4", "audio/ogg", "audio/webm", "audio/wav", "audio/x-wav")
    return f.get("content_type", "").lower() in types


async def _check_file(file_id, station):
    f = await db.files.find_one({"id": file_id, "user_id": station["owner_id"]}, {"_id": 0})
    if not eligible_file(f, station):
        raise HTTPException(422, "Select an eligible media upload from your account")
    return f


def playout(s, active, live_url, current, next_program, files, clock):
    """A real public live session always overrides the time-based schedule."""
    if active and live_url:
        return {"mode": "live", "key": active["content_id"], "title": active["title"], "url": live_url}
    if not s.get("automation_enabled"):
        return None
    scheduled = current and current.get("format") == "prerecorded" and files.get(current.get("file_id"))
    fallback = files.get(s.get("fallback_file_id"))
    if eligible_file(scheduled, s):
        return {"mode": "scheduled", "key": current["id"], "title": current["title"], "url": "/api/files/" + scheduled["storage_path"], "anchor": current["start"], "until": current["end"]}
    if eligible_file(fallback, s):
        return {"mode": "fallback", "key": fallback["id"], "title": "Continuous programming", "url": "/api/files/" + fallback["storage_path"], "anchor": s.get("automation_anchor") or s["created_at"], "until": current["end"] if current else next_program["start"] if next_program else None}
    return None


def programme(body: ProgrammeIn) -> dict:
    if not body.title.strip() or body.start.tzinfo is None or body.end.tzinfo is None:
        raise HTTPException(422, "Enter a title and start/end times with time zones")
    start, end = body.start.astimezone(timezone.utc), body.end.astimezone(timezone.utc)
    if not start < end <= start + timedelta(hours=24):
        raise HTTPException(422, "Programmes must be between 1 second and 24 hours")
    if end <= now() or start > now() + timedelta(days=365):
        raise HTTPException(422, "Choose a current or future programme within one year")
    return {"id": uid(), "title": body.title.strip(), "description": body.description.strip(),
            "start": start.isoformat(), "end": end.isoformat(), "format": body.format, "file_id": body.file_id}


def overlaps(a, b):
    return a["start"] < b["end"] and b["start"] < a["end"]


async def _owned(station_id, user):
    station = await db.stations.find_one({"id": station_id, "owner_id": user["id"]}, {"_id": 0})
    if not station:
        raise HTTPException(404, "Station not found")
    return station


async def _decorate(stations, *, private=False):
    if not stations:
        return []
    owners = {s["owner_id"] for s in stations}
    allowed = {u["id"] for u in await db.users.find({"id": {"$in": list(owners)}, "suspended": {"$ne": True}, "broadcast_blocked": {"$ne": True}}, {"id": 1}).to_list(len(owners))}
    sessions = await db.broadcast_sessions.find({"owner_id": {"$in": list(owners)}, "status": "live", "visibility": "public"},
         {"_id": 0, "owner_id": 1, "kind": 1, "content_id": 1, "title": 1}).sort("started_at", -1).to_list(2 * len(owners))
    content_ids = [s["content_id"] for s in sessions if s.get("content_id")]
    published = {c["id"]: c.get("stream_url") for c in await db.content.find({"id": {"$in": content_ids}, "gated": {"$ne": True}}, {"id": 1, "stream_url": 1}).to_list(len(content_ids) or 1)}
    live = {(s["owner_id"], s["kind"]): s for s in reversed(sessions) if s.get("content_id") in published}
    t = now_iso()
    media_ids = {p.get("file_id") for s in stations for p in s.get("programmes", []) if p.get("end", "") > t}
    media_ids.update(s.get("fallback_file_id") for s in stations)
    media_ids.discard(None)
    files = {f["id"]: f for f in await db.files.find({"id": {"$in": list(media_ids)}}, {"_id": 0}).to_list(len(media_ids) or 1)}
    result = []
    for s in stations:
        visible = not s.get("hidden") and s["owner_id"] in allowed
        if not visible and not private:
            continue
        programmes = sorted((p for p in s.get("programmes", []) if p["end"] > t), key=lambda p: p["start"])
        active = live.get((s["owner_id"], s["kind"])) if visible else None
        current = next((p for p in programmes if p["start"] <= t < p["end"]), None)
        upcoming = next((p for p in programmes if p["start"] > t), None)
        stream_url = published.get(active["content_id"]) if active else None
        source = playout(s, active, stream_url, current, upcoming, files, t) if visible else None
        view = {k: s.get(k) for k in ("id", "kind", "name", "description", "logo_url", "banner_url", "category", "channel_id")}
        view.update({"on_air": bool(active or source), "live_content_id": active.get("content_id") if active else None,
                     "live_title": active.get("title") if active else (source or {}).get("title"), "programmes": programmes if private else programmes[:30],
                     "playout": source, "as_of": t,
                     "now": next((p for p in programmes if p["start"] <= t < p["end"]), None),
                     "next": next((p for p in programmes if p["start"] > t), None)})
        if private:
            view.update({"owner_id": s["owner_id"], "hidden": bool(s.get("hidden")), "visible": visible,
                         "moderation_reason": s.get("moderation_reason"), "automation_enabled": bool(s.get("automation_enabled")), "fallback_file_id": s.get("fallback_file_id"), "starter_available": s["id"] in STARTER_MEDIA})
        result.append(view)
    return result


@router.get("/stations")
async def directory(kind: Kind | None = None, offset: int = 0):
    q = {"hidden": {"$ne": True}}
    if kind:
        q["kind"] = kind
    rows = await db.stations.find(q, {"_id": 0}).sort("created_at", 1).skip(max(0, offset)).limit(100).to_list(100)
    return {"stations": await _decorate(rows), "has_more": len(rows) == 100, "as_of": now_iso()}


@router.get("/stations/{station_id}")
async def public_station(station_id: str):
    row = await db.stations.find_one({"id": station_id, "hidden": {"$ne": True}}, {"_id": 0})
    data = await _decorate([row] if row else [])
    if not data:
        raise HTTPException(404, "Station not found")
    return data[0]


@router.get("/creator/stations")
async def creator_stations(user=Depends(get_user)):
    return await _decorate(await db.stations.find({"owner_id": user["id"]}, {"_id": 0}).to_list(2), private=True)


@router.put("/creator/stations/{kind}")
async def save_station(kind: Kind, body: StationIn, user=Depends(get_user)):
    if user.get("broadcast_blocked"):
        raise HTTPException(403, "Your broadcasting permission is restricted")
    # One permanent station of each type per account; retries keep the same ID.
    sid = str(uuid5(NAMESPACE_URL, f"lono:station:{user['id']}:{kind}"))
    ch = await _channel_for(user)
    data = body.model_dump()
    for key in ("logo_url", "banner_url"):
        if data[key].startswith("/api/files/"):
            file = await db.files.find_one({"storage_path": data[key].removeprefix("/api/files/"), "user_id": user["id"], "is_deleted": {"$ne": True}, "pending": {"$ne": True}, "content_type": {"$regex": "^image/"}})
            if not file:
                raise HTTPException(422, "Choose an image uploaded by your account")
    try:
        await db.stations.update_one({"_id": sid}, {"$set": {**data, "updated_at": now_iso()}, "$setOnInsert": {
            "id": sid, "owner_id": user["id"], "channel_id": ch["id"], "kind": kind, "created_at": now_iso(),
            "hidden": False, "programmes": [], "revision": 0}}, upsert=True)
    except DuplicateKeyError:
        raise HTTPException(409, "Station changed concurrently; retry")
    await audit("station_saved", user, target=sid)
    return (await _decorate([await _owned(sid, user)], private=True))[0]


@router.post("/creator/stations/{station_id}/programmes")
async def add_programme(station_id: str, body: ProgrammeIn, user=Depends(get_user)):
    if user.get("broadcast_blocked"):
        raise HTTPException(403, "Your broadcasting permission is restricted")
    s = await _owned(station_id, user)
    p = programme(body)
    if body.file_id:
        if body.format != "prerecorded":
            raise HTTPException(422, "Media can only be attached to a prerecorded programme")
        await _check_file(body.file_id, s)
    items = [x for x in s.get("programmes", []) if x["end"] > now_iso()]
    if len(items) >= 100:
        raise HTTPException(409, "Maximum of 100 upcoming programmes")
    if any(overlaps(x, p) for x in items):
        raise HTTPException(409, "Programme overlaps an existing listing")
    result = await db.stations.update_one({"id": station_id, "revision": s["revision"]}, {"$set": {"programmes": sorted(items + [p], key=lambda x: x["start"])}, "$inc": {"revision": 1}})
    if not result.matched_count:
        raise HTTPException(409, "Schedule changed; refresh and retry")
    return p


@router.get("/creator/stations/{station_id}/media")
async def media_library(station_id: str, user=Depends(get_user)):
    s = await _owned(station_id, user)
    q = {"user_id": user["id"], "storage_path": {"$regex": "^uploads/"}, "is_deleted": False, "pending": {"$ne": True}, "protected": {"$ne": True}}
    rows = await db.files.find(q, {"_id": 0, "id": 1, "user_id": 1, "storage_path": 1, "content_type": 1, "original_filename": 1}).sort("created_at", -1).to_list(500)
    return [{"id": f["id"], "name": f.get("original_filename", "Media"), "content_type": f["content_type"]} for f in rows if eligible_file(f, s)]


@router.put("/creator/stations/{station_id}/automation")
async def configure_automation(station_id: str, body: AutomationIn, user=Depends(get_user)):
    if user.get("broadcast_blocked"):
        raise HTTPException(403, "Your broadcasting permission is restricted")
    s = await _owned(station_id, user)
    if body.fallback_file_id:
        await _check_file(body.fallback_file_id, s)
    fields = {"automation_enabled": body.enabled, "fallback_file_id": body.fallback_file_id}
    if body.fallback_file_id != s.get("fallback_file_id") or not s.get("automation_anchor"):
        fields["automation_anchor"] = now_iso()
    await db.stations.update_one({"id": station_id, "owner_id": user["id"]}, {"$set": fields})
    await audit("station_automation_changed", user, target=station_id, details={"enabled": body.enabled, "fallback": bool(body.fallback_file_id)})
    return {"ok": True}


@router.post("/creator/stations/{station_id}/starter-media")
async def import_starter_media(station_id: str, user=Depends(get_user)):
    """Copy the approved, bundled flagship ident into its owner's media library."""
    s = await _owned(station_id, user)
    if user.get("broadcast_blocked") or s.get("hidden"):
        raise HTTPException(403, "Station broadcasting is restricted")
    item = STARTER_MEDIA.get(station_id)
    if not item:
        raise HTTPException(404, "No starter media for this station")
    filename, content_type = item
    path = Path(__file__).resolve().parent.parent / "station_assets" / filename
    if not path.is_file():
        raise HTTPException(503, "Starter media is not installed")
    existing = await db.files.find_one({"user_id": user["id"], "station_starter": station_id, "is_deleted": False, "pending": {"$ne": True}})
    if eligible_file(existing, s) and await storage.exists(existing["storage_path"]):
        return {"file_id": existing["id"]}
    fid = uid()
    key = f"uploads/{user['id']}/{fid}{path.suffix}"
    data = path.read_bytes()
    await storage.put(key, data, content_type)
    await db.files.insert_one({"id": fid, "user_id": user["id"], "storage_path": key, "original_filename": filename,
                               "content_type": content_type, "size": len(data), "is_deleted": False, "created_at": now_iso(), "station_starter": station_id})
    await audit("station_starter_imported", user, target=station_id)
    return {"file_id": fid}


@router.delete("/creator/stations/{station_id}/programmes/{programme_id}")
async def remove_programme(station_id: str, programme_id: str, user=Depends(get_user)):
    await _owned(station_id, user)
    result = await db.stations.update_one({"id": station_id, "owner_id": user["id"], "programmes.id": programme_id}, {"$pull": {"programmes": {"id": programme_id}}, "$inc": {"revision": 1}})
    if not result.matched_count:
        raise HTTPException(404, "Programme not found")
    return {"ok": True}


class ModerationIn(BaseModel):
    hidden: bool
    reason: str = Field(min_length=3, max_length=500)


@router.get("/admin/stations")
async def admin_stations(offset: int = 0, admin=Depends(get_admin)):
    rows = await db.stations.find({}, {"_id": 0}).sort("created_at", -1).skip(max(0, offset)).limit(100).to_list(100)
    return {"stations": await _decorate(rows, private=True), "has_more": len(rows) == 100}


@router.post("/admin/stations/{station_id}/visibility")
async def moderate_station(station_id: str, body: ModerationIn, admin=Depends(get_admin)):
    reason = body.reason.strip()
    if len(reason) < 3:
        raise HTTPException(422, "Enter a reason")
    result = await db.stations.update_one({"id": station_id}, {"$set": {"hidden": body.hidden, "moderation_reason": reason}})
    if not result.matched_count:
        raise HTTPException(404, "Station not found")
    await audit("station_visibility_changed", admin, target=station_id, details={"hidden": body.hidden, "reason": reason})
    return {"ok": True}
