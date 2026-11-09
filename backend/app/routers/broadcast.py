"""Creator broadcasting: ingest (encoder or browser), private test sessions,
going live on LoNo, simulcasting to destinations, recording.

Viewer playback never calls anything here except reading HLS through /media,
so channel switching or leaving a player can't affect a broadcast."""
import asyncio
import ipaddress
import os
import re
import secrets
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from .. import config
from ..audit import audit
from ..broadcast import media
from ..broadcast.platforms import BY_ID, PLATFORMS, target_url
from ..broadcast.relays import manager
from ..broadcast.secrets_box import decrypt, encrypt, hash_key, hint, new_stream_key, redact, sign, verify
from ..db import db
from ..security import get_user
from ..storage import storage
from ..util import now, now_iso, uid
from .creator import _channel_for

router = APIRouter(prefix="/broadcast", tags=["broadcast"])
media_router = APIRouter(tags=["broadcast"])          # /media/hls/... (not under /api)
ACTIVE = ("created", "live")
INTERNAL_USER = "lono-internal"


# ---------------------------------------------------------------- helpers
def _require_media():
    if not config.MEDIA_ENABLED:
        raise HTTPException(503, "Live broadcasting is off on this server. Set MEDIA_ENABLED=true and run the media server (see docs/BROADCAST.md).")


async def _ingest_for(user) -> dict:
    ing = await db.ingests.find_one({"owner_id": user["id"]}, {"_id": 0})
    if ing:
        return ing
    key = new_stream_key()
    ing = {"id": "in" + secrets.token_hex(5), "owner_id": user["id"], "key_enc": encrypt(key), "key_hash": hash_key(key),
           "key_hint": hint(key), "created_at": now_iso(), "rotated_at": None}
    await db.ingests.insert_one(dict(ing))
    return ing


def _ingest_view(ing: dict) -> dict:
    key = decrypt(ing["key_enc"])
    obs_key = f"{ing['id']}?key={key}"
    return {
        "ingest_id": ing["id"], "key_hint": ing["key_hint"], "rotated_at": ing.get("rotated_at"),
        "rtmp": {"server": config.INGEST_RTMP_URL, "stream_key": obs_key},
        "rtmps": {"server": config.INGEST_RTMPS_URL, "stream_key": obs_key} if config.INGEST_RTMPS_URL else None,
        "srt": {"url": f"{config.INGEST_SRT_URL}?streamid=publish:live/{ing['id']}:{ing['id']}:{key}"},
        "path": f"live/{ing['id']}",
    }


def _internal_src(ingest_id: str, path: str | None = None) -> str:
    return f"{config.MEDIA_RTMP_INTERNAL}/{path or 'live/' + ingest_id}?user={INTERNAL_USER}&pass={config.MEDIA_INTERNAL_SECRET}"


def needs_transcode(tracks: list[str] | None) -> bool:
    """Browser feeds (VP8/VP9 video, Opus audio) can't go over RTMP or (VP8) into HLS."""
    t = [x.lower() for x in (tracks or [])]
    return any(x in ("vp8", "vp9", "av1", "h265", "opus", "g711", "lpcm") for x in t)


def _transcode_args(ingest_id: str) -> list[str]:
    auth = f"{INTERNAL_USER}:{config.MEDIA_INTERNAL_SECRET}@"
    base = config.MEDIA_RTSP_INTERNAL.replace("rtsp://", "rtsp://" + auth)
    return ["-hide_banner", "-nostats", "-loglevel", "warning", "-progress", "pipe:1", "-rtsp_transport", "tcp",
            "-i", f"{base}/live/{ingest_id}",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-g", "60", "-b:v", "2500k", "-maxrate", "3000k",
            "-bufsize", "5000k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-f", "rtsp", "-rtsp_transport", "tcp", f"{base}/tx/{ingest_id}"]


async def ensure_media_path(s: dict) -> str:
    """Pick the stream everything reads: the creator's feed as-is (H.264/AAC from
    encoders), or a single converted copy for browser feeds."""
    feed = await media.path_info(f"live/{s['ingest_id']}") or {}
    if not feed.get("ready"):
        return s.get("media_path") or f"live/{s['ingest_id']}"
    if not needs_transcode(feed.get("tracks")):
        path = f"live/{s['ingest_id']}"
    else:
        path = f"tx/{s['ingest_id']}"
        await manager.start(s["id"], "transcode", _transcode_args(s["ingest_id"]))
        for _ in range(30):                      # wait until the converted stream exists
            info = await media.path_info(path)
            if info and info.get("ready"):
                break
            await asyncio.sleep(0.5)
    if s.get("media_path") != path:
        await db.broadcast_sessions.update_one({"id": s["id"]}, {"$set": {"media_path": path}})
        s["media_path"] = path
    return path


def _codec_args(tracks: list[str] | None) -> list[str]:
    """Copy H.264/AAC (encoders like OBS). Browser sources send Opus audio and
    sometimes VP8/VP9 video, which RTMP platforms don't accept: convert those."""
    t = [x.lower() for x in (tracks or [])]
    video_ok = not any(x in ("vp8", "vp9", "av1", "h265") for x in t)
    audio_ok = not any(x in ("opus", "g711", "lpcm") for x in t)
    v = ["-c:v", "copy"] if video_ok else ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-g", "60", "-b:v", "2500k", "-pix_fmt", "yuv420p"]
    a = ["-c:a", "copy"] if audio_ok else ["-c:a", "aac", "-b:a", "128k", "-ar", "48000"]
    return v + a


def _relay_args(src: str, dest: str, tracks: list[str] | None = None) -> list[str]:
    fmt = "mpegts" if dest.startswith("srt://") else "flv"
    return ["-hide_banner", "-nostats", "-loglevel", "warning", "-progress", "pipe:1", "-rw_timeout", "15000000",
            "-i", src, *_codec_args(tracks), "-f", fmt, dest]


def _recorder_args(src: str, out: str) -> list[str]:
    return ["-hide_banner", "-nostats", "-loglevel", "warning", "-progress", "pipe:1", "-rw_timeout", "15000000",
            "-i", src, "-c", "copy", "-movflags", "+frag_keyframe+empty_moov+default_base_moof", "-f", "mp4", out]


async def _event(session: dict, type_: str, **details):
    ev = {"id": uid(), "session_id": session["id"], "owner_id": session["owner_id"], "type": type_,
          "at": now_iso(), "details": details}
    await db.broadcast_events.insert_one(dict(ev))
    from ..broadcast import webhooks  # delivered to the creator's integrations (phase 3)
    await webhooks.dispatch(ev)


async def _session(session_id: str, user) -> dict:
    s = await db.broadcast_sessions.find_one({"id": session_id, "owner_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Broadcast session not found")
    return s


async def _session_view(s: dict) -> dict:
    ing = await db.ingests.find_one({"id": s["ingest_id"]}, {"_id": 0})
    feed = await media.path_info(f"live/{s['ingest_id']}") if config.MEDIA_ENABLED else None
    relays = manager.get(s["id"])
    dests = []
    for d in s.get("destinations", []):
        st = relays.get(f"dest:{d['id']}") or {"state": "idle" if s["status"] != "live" else "waiting", "error": None, "attempts": 0}
        dests.append({**d, **st})
    token = f"{s['id']}.{sign(s['id'] + s['ingest_id'])}"
    return {
        **{k: v for k, v in s.items() if k not in ("idempotency_key",)},
        "feed": {**(feed or {"ready": False}), "converted": (s.get("media_path") or "").startswith("tx/")},
        "destinations": dests,
        "recorder": relays.get("recorder"),
        "preview_url": f"/media/hls/t/{token}/{s['ingest_id']}/index.m3u8",
        "public_url": f"/media/hls/{s['ingest_id']}/index.m3u8" if s.get("visibility") == "public" else None,
        "ingest": {"key_hint": ing["key_hint"]} if ing else None,
    }


async def _start_targets(s: dict):
    path = await ensure_media_path(s)
    src = _internal_src(s["ingest_id"], path)
    feed = await media.path_info(path) or {}
    tracks = feed.get("tracks")
    for d in s.get("destinations", []):
        dest = await db.destinations.find_one({"id": d["id"], "owner_id": s["owner_id"]})
        if not dest or not BY_ID.get(dest["platform"], {}).get("supported"):
            continue
        key = decrypt(dest["key_enc"])
        await manager.start(s["id"], f"dest:{d['id']}", _relay_args(src, target_url(dest["server_url"], key), tracks), (key,))
    if s.get("record"):
        folder = Path(config.RECORDINGS_DIR) / s["id"]
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / f"part_{len(list(folder.glob('part_*.mp4'))):03d}.mp4"
        await manager.start(s["id"], "recorder", _recorder_args(src, str(part)))


# ---------------------------------------------------------------- ingest
@router.get("/ingest")
async def get_ingest(user=Depends(get_user)):
    return _ingest_view(await _ingest_for(user))


@router.post("/ingest/rotate")
async def rotate_key(user=Depends(get_user)):
    ing = await _ingest_for(user)
    live = await db.broadcast_sessions.find_one({"owner_id": user["id"], "status": "live"})
    if live:
        raise HTTPException(409, "End the live broadcast before rotating the stream key")
    key = new_stream_key()
    await db.ingests.update_one({"id": ing["id"]}, {"$set": {
        "key_enc": encrypt(key), "key_hash": hash_key(key), "key_hint": hint(key), "rotated_at": now_iso()}})
    await audit("stream_key_rotated", user, target=ing["id"])
    return _ingest_view(await db.ingests.find_one({"id": ing["id"]}, {"_id": 0}))


# ---------------------------------------------------------------- destinations
class DestinationIn(BaseModel):
    platform: str
    name: str = Field(default="", max_length=60)
    server_url: str = Field(min_length=6, max_length=500)
    stream_key: str = Field(default="", max_length=500)


def _dest_view(d: dict) -> dict:
    p = BY_ID.get(d["platform"], {})
    return {"id": d["id"], "platform": d["platform"], "platform_name": p.get("name"), "name": d["name"],
            "server_url": d["server_url"], "key_hint": d.get("key_hint"), "supported": p.get("supported", False),
            "created_at": d["created_at"]}


@router.get("/platforms")
async def platforms():
    return PLATFORMS


@router.get("/destinations")
async def list_destinations(user=Depends(get_user)):
    return [_dest_view(d) for d in await db.destinations.find({"owner_id": user["id"]}).to_list(100)]


@router.post("/destinations")
async def add_destination(body: DestinationIn, user=Depends(get_user)):
    p = BY_ID.get(body.platform)
    if not p:
        raise HTTPException(422, "Unknown destination")
    if not p["supported"]:
        raise HTTPException(422, p["where"])
    url = body.server_url.strip()
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if scheme not in p["protocols"]:
        raise HTTPException(422, f"{p['name']} needs a server URL starting with " + " or ".join(f"{x}://" for x in p["protocols"]))
    key = body.stream_key.strip()
    d = {"id": uid(), "owner_id": user["id"], "platform": p["id"], "name": body.name.strip() or p["name"],
         "server_url": url, "key_enc": encrypt(key), "key_hint": hint(key) if key else None, "created_at": now_iso()}
    await db.destinations.insert_one(dict(d))
    await audit("destination_added", user, target=d["id"], details={"platform": p["id"]})
    return _dest_view(d)


@router.delete("/destinations/{dest_id}")
async def remove_destination(dest_id: str, user=Depends(get_user)):
    res = await db.destinations.delete_one({"id": dest_id, "owner_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Destination not found")
    return {"ok": True}


# ---------------------------------------------------------------- sessions
class SessionIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="Live", max_length=60)
    kind: Literal["live_tv", "live_radio"] = "live_tv"
    test: bool = False                              # private test: no public page, no simulcast
    destination_ids: list[str] = Field(default_factory=list, max_length=12)
    record: bool = False
    scheduled_for: str | None = None


async def create_session_for(user, body: SessionIn, idempotency_key: str | None = None) -> dict:
    _require_media()
    if idempotency_key:
        prev = await db.broadcast_sessions.find_one({"owner_id": user["id"], "idempotency_key": idempotency_key}, {"_id": 0})
        if prev:
            return prev
    active = await db.broadcast_sessions.find_one({"owner_id": user["id"], "status": {"$in": list(ACTIVE)}}, {"_id": 0})
    if active:
        raise HTTPException(409, f"You already have an open broadcast session ({active['title']}). End it first.")
    dests = []
    if not body.test:
        for did in body.destination_ids:
            d = await db.destinations.find_one({"id": did, "owner_id": user["id"]})
            if not d:
                raise HTTPException(422, "One of the selected destinations doesn't exist")
            if not BY_ID[d["platform"]]["supported"]:
                raise HTTPException(422, f"{BY_ID[d['platform']]['name']} can't be simulcast to")
            dests.append({"id": d["id"], "platform": d["platform"], "name": d["name"]})
    ing = await _ingest_for(user)
    s = {"id": uid(), "owner_id": user["id"], "ingest_id": ing["id"], "title": body.title.strip(),
         "description": body.description.strip(), "category": body.category, "kind": body.kind,
         "visibility": "test" if body.test else "public", "destinations": dests, "record": body.record and not body.test,
         "status": "created", "scheduled_for": body.scheduled_for, "created_at": now_iso(),
         "started_at": None, "ended_at": None, "content_id": None, "recording_id": None,
         "idempotency_key": idempotency_key}
    await db.broadcast_sessions.insert_one(dict(s))
    await audit("broadcast_session_created", user, target=s["id"], details={"test": body.test, "destinations": len(dests)})
    if config.MEDIA_ENABLED:
        asyncio.create_task(ensure_media_path(dict(s)))
    return s


@router.post("/sessions")
async def create_session(body: SessionIn, user=Depends(get_user), idempotency_key: str | None = Header(default=None)):
    return await _session_view(await create_session_for(user, body, idempotency_key))


@router.get("/sessions")
async def list_sessions(user=Depends(get_user)):
    items = await db.broadcast_sessions.find({"owner_id": user["id"]}, {"_id": 0, "idempotency_key": 0}).sort("created_at", -1).to_list(50)
    return items


@router.get("/sessions/current")
async def current_session(user=Depends(get_user)):
    s = await db.broadcast_sessions.find_one({"owner_id": user["id"], "status": {"$in": list(ACTIVE)}}, {"_id": 0})
    return await _session_view(s) if s else None


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user=Depends(get_user)):
    return await _session_view(await _session(session_id, user))


async def start_session_for(user, session_id: str) -> dict:
    _require_media()
    s = await _session(session_id, user)
    if s["status"] == "live":
        return s                                    # starting twice is safe
    if s["status"] != "created":
        raise HTTPException(409, "This session has ended. Create a new one.")
    if s["visibility"] == "test":
        raise HTTPException(409, "Test sessions stay private. Create a broadcast session to go live.")
    feed = await media.path_info(f"live/{s['ingest_id']}")
    if not feed or not feed["ready"]:
        raise HTTPException(409, "No feed from your encoder or camera yet. Start sending, check the preview, then go live.")
    await ensure_media_path(s)
    ch = await _channel_for(user)
    content = {"id": uid(), "title": s["title"], "description": s["description"] or "Live on LoNo", "kind": s["kind"],
               "category": s["category"], "thumbnail_url": ch.get("avatar_url") or "/icons/icon-512.png",
               "stream_url": f"/media/hls/{s['ingest_id']}/index.m3u8", "duration_sec": 0, "is_original": False,
               "is_premium": False, "channel_id": ch["id"], "views": 0, "likes": 0, "rating": None,
               "year": now().year, "created_at": now_iso(), "broadcast_session_id": s["id"]}
    await db.content.insert_one(dict(content))
    await db.broadcast_sessions.update_one({"id": s["id"], "status": "created"}, {"$set": {
        "status": "live", "started_at": now_iso(), "content_id": content["id"]}})
    s = await _session(session_id, user)
    await _start_targets(s)
    await _event(s, "broadcast.started", title=s["title"], destinations=[d["platform"] for d in s["destinations"]])
    await audit("broadcast_started", user, target=s["id"])
    return s


@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str, user=Depends(get_user)):
    return await _session_view(await start_session_for(user, session_id))


async def stop_session_for(user, session_id: str) -> dict:
    s = await _session(session_id, user)
    if s["status"] == "ended":
        return s                                    # stopping twice is safe
    await manager.stop(s["id"])
    if s.get("content_id"):
        await db.content.delete_one({"id": s["content_id"]})
    await db.broadcast_sessions.update_one({"id": s["id"]}, {"$set": {"status": "ended", "ended_at": now_iso(), "content_id": None}})
    s = await _session(session_id, user)
    await _event(s, "broadcast.ended", title=s["title"])
    if s.get("record") and s.get("started_at"):
        asyncio.create_task(_finalize_recording(s))
    return s


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str, user=Depends(get_user)):
    return await _session_view(await stop_session_for(user, session_id))


@router.post("/sessions/{session_id}/destinations/{dest_id}/retry")
async def retry_destination(session_id: str, dest_id: str, user=Depends(get_user)):
    s = await _session(session_id, user)
    if s["status"] != "live":
        raise HTTPException(409, "The broadcast isn't live")
    if dest_id not in {d["id"] for d in s["destinations"]}:
        raise HTTPException(404, "That destination isn't part of this broadcast")
    dest = await db.destinations.find_one({"id": dest_id, "owner_id": user["id"]})
    if not dest:
        raise HTTPException(404, "That destination was removed")
    key = decrypt(dest["key_enc"])
    await manager.stop(s["id"], f"dest:{dest_id}")
    path = s.get("media_path") or f"live/{s['ingest_id']}"
    feed = await media.path_info(path) or {}
    await manager.start(s["id"], f"dest:{dest_id}", _relay_args(_internal_src(s["ingest_id"], path), target_url(dest["server_url"], key), feed.get("tracks")), (key,))
    return await _session_view(s)


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str, user=Depends(get_user)):
    await _session(session_id, user)
    return await db.broadcast_events.find({"session_id": session_id}, {"_id": 0}).sort("at", 1).to_list(500)


# ---------------------------------------------------------------- browser camera (WHIP)
_whip_resources: dict[str, str] = {}   # user id -> MediaMTX WHIP resource URL


@router.post("/whip")
async def whip_publish(request: Request, user=Depends(get_user)):
    """Creator Studio sends its WebRTC offer here; LoNo forwards it to the media
    server with the creator's stream key, so the key never reaches the browser."""
    _require_media()
    s = await db.broadcast_sessions.find_one({"owner_id": user["id"], "status": {"$in": list(ACTIVE)}}, {"_id": 0})
    if not s:
        raise HTTPException(409, "Create a test or live session first")
    ing = await db.ingests.find_one({"id": s["ingest_id"]})
    offer = (await request.body()).decode(errors="ignore")
    if not offer.startswith("v=0"):
        raise HTTPException(422, "Expected an SDP offer")
    url = f"{config.MEDIA_WEBRTC_URL}/live/{ing['id']}/whip"
    try:
        async with httpx.AsyncClient(timeout=15, auth=(ing["id"], decrypt(ing["key_enc"]))) as hc:
            r = await hc.post(url, content=offer, headers={"Content-Type": "application/sdp"})
    except httpx.HTTPError:
        raise HTTPException(502, "The media server isn't responding")
    if r.status_code not in (200, 201):
        raise HTTPException(502, f"The media server refused the camera stream ({r.status_code})")
    loc = r.headers.get("location")
    if loc:
        _whip_resources[user["id"]] = loc if loc.startswith("http") else config.MEDIA_WEBRTC_URL + loc
    return Response(r.text, status_code=201, media_type="application/sdp")


@router.delete("/whip")
async def whip_stop(user=Depends(get_user)):
    loc = _whip_resources.pop(user["id"], None)
    if loc:
        ing = await db.ingests.find_one({"owner_id": user["id"]})
        try:
            async with httpx.AsyncClient(timeout=5, auth=(ing["id"], decrypt(ing["key_enc"]))) as hc:
                await hc.delete(loc)
        except httpx.HTTPError:
            pass
    return {"ok": True}


# ---------------------------------------------------------------- recordings
async def _finalize_recording(s: dict):
    folder = Path(config.RECORDINGS_DIR) / s["id"]
    rec = {"id": uid(), "session_id": s["id"], "owner_id": s["owner_id"], "title": s["title"], "status": "processing",
           "visibility": "private", "publish_at": None, "content_id": None, "created_at": now_iso(),
           "duration_sec": 0, "size": 0, "url": None}
    await db.recordings.insert_one(dict(rec))
    await db.broadcast_sessions.update_one({"id": s["id"]}, {"$set": {"recording_id": rec["id"]}})
    await asyncio.sleep(1.5)                         # let the recorder flush its last fragment
    parts = sorted(p for p in folder.glob("part_*.mp4") if p.stat().st_size > 1024)
    if not parts:
        await db.recordings.update_one({"id": rec["id"]}, {"$set": {"status": "failed", "error": "Nothing was recorded"}})
        return
    listfile = folder / "parts.txt"
    listfile.write_text("".join(f"file '{p.name}'\n" for p in parts))
    out = folder / "recording.mp4"
    proc = await asyncio.create_subprocess_exec(config.FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                                                "-safe", "0", "-i", str(listfile), "-c", "copy", "-movflags", "+faststart", str(out),
                                                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0 or not out.exists():
        await db.recordings.update_one({"id": rec["id"]}, {"$set": {"status": "failed", "error": "Couldn't assemble the recording"}})
        return
    probe = await asyncio.create_subprocess_exec("ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                 "-of", "default=nw=1:nk=1", str(out), stdout=asyncio.subprocess.PIPE)
    dur = (await probe.communicate())[0].decode().strip()
    key = f"recordings/{s['owner_id']}/{s['id']}.mp4"
    data = out.read_bytes()
    await storage.put(key, data, "video/mp4")
    await db.files.insert_one({"id": uid(), "user_id": s["owner_id"], "storage_path": key, "original_filename": f"{s['title']}.mp4",
                               "content_type": "video/mp4", "size": len(data), "is_deleted": False, "created_at": now_iso()})
    await db.recordings.update_one({"id": rec["id"]}, {"$set": {
        "status": "ready", "url": f"/api/files/{key}", "size": len(data),
        "duration_sec": int(float(dur)) if dur else 0, "parts": len(parts)}})
    shutil.rmtree(folder, ignore_errors=True)
    await _event({**s}, "recording.ready", recording_id=rec["id"], duration_sec=int(float(dur)) if dur else 0)


class PublishIn(BaseModel):
    when: Literal["now", "schedule", "private"]
    publish_at: str | None = None                    # ISO time, for "schedule"
    title: str | None = Field(default=None, max_length=140)


async def _publish_recording(rec: dict):
    s = await db.broadcast_sessions.find_one({"id": rec["session_id"]}) or {}
    owner = await db.users.find_one({"id": rec["owner_id"]})
    ch = await _channel_for(owner) if owner else {}
    content = {"id": uid(), "title": rec["title"], "description": s.get("description") or "Recorded live on LoNo",
               "kind": "podcast" if s.get("kind") == "live_radio" else "short", "category": s.get("category", "Live"),
               "thumbnail_url": ch.get("avatar_url") or "/icons/icon-512.png", "stream_url": rec["url"],
               "duration_sec": rec.get("duration_sec", 0), "is_original": False, "is_premium": False,
               "channel_id": ch.get("id"), "views": 0, "likes": 0, "rating": None, "year": now().year,
               "created_at": now_iso(), "recording_id": rec["id"]}
    await db.content.insert_one(dict(content))
    await db.recordings.update_one({"id": rec["id"]}, {"$set": {"visibility": "public", "content_id": content["id"], "publish_at": None}})


@router.get("/recordings")
async def recordings(user=Depends(get_user)):
    return await db.recordings.find({"owner_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.post("/recordings/{rec_id}/publish")
async def publish_recording(rec_id: str, body: PublishIn, user=Depends(get_user)):
    rec = await db.recordings.find_one({"id": rec_id, "owner_id": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Recording not found")
    if rec["status"] != "ready":
        raise HTTPException(409, "The recording isn't ready yet")
    if body.title:
        await db.recordings.update_one({"id": rec_id}, {"$set": {"title": body.title.strip()}})
        rec["title"] = body.title.strip()
    if body.when == "private":
        if rec.get("content_id"):
            await db.content.delete_one({"id": rec["content_id"]})
        await db.recordings.update_one({"id": rec_id}, {"$set": {"visibility": "private", "content_id": None, "publish_at": None}})
    elif body.when == "now":
        if not rec.get("content_id"):
            await _publish_recording(rec)
    else:
        try:
            when = datetime.fromisoformat(body.publish_at or "")
        except ValueError:
            raise HTTPException(422, "Give a valid date and time to publish")
        if when.tzinfo is None:
            raise HTTPException(422, "Include a time zone in the publish time")
        await db.recordings.update_one({"id": rec_id}, {"$set": {"visibility": "scheduled", "publish_at": when.isoformat()}})
    await audit(f"recording_{body.when}", user, target=rec_id)
    return await db.recordings.find_one({"id": rec_id}, {"_id": 0})


async def publish_due_recordings():
    async for rec in db.recordings.find({"visibility": "scheduled", "publish_at": {"$lte": now_iso()}}, {"_id": 0}):
        await _publish_recording(rec)


# ---------------------------------------------------------------- media server callbacks
def _from_private_network(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return host in ("testclient", "localhost")


@router.post("/mtx/auth", include_in_schema=False)
async def mtx_auth(request: Request):
    """MediaMTX asks LoNo whether a publisher/reader is allowed (authMethod: http)."""
    if not _from_private_network(request):
        raise HTTPException(403)
    b = await request.json()
    user, password, action, path = b.get("user") or "", b.get("password") or "", b.get("action"), b.get("path") or ""
    if user == INTERNAL_USER and secrets.compare_digest(password, config.MEDIA_INTERNAL_SECRET):
        return Response(status_code=204)
    if action == "publish" and path.startswith("room/"):
        from .rooms import mtx_publish_allowed
        if await mtx_publish_allowed(path, user, password):
            return Response(status_code=204)
        raise HTTPException(401)
    if action == "publish" and re.fullmatch(r"live/in[0-9a-f]{10}", path):
        key = password or (parse_qs(b.get("query") or "").get("key") or [""])[0]
        ing = await db.ingests.find_one({"id": path.split("/", 1)[1]})
        if ing and key and secrets.compare_digest(hash_key(key), ing["key_hash"]):
            owner = await db.users.find_one({"id": ing["owner_id"]}, {"suspended": 1})
            if owner and not owner.get("suspended"):
                return Response(status_code=204)
    raise HTTPException(401)


async def on_feed_change(path: str, ready: bool):
    """Encoder connected/disconnected. Reconnect relays and recording when a live feed returns."""
    if not path.startswith("live/"):
        return
    ingest_id = path.split("/", 1)[1]
    s = await db.broadcast_sessions.find_one({"ingest_id": ingest_id, "status": {"$in": list(ACTIVE)}}, {"_id": 0})
    if not s:
        return
    await _event(s, "stream.connected" if ready else "stream.disconnected")
    if ready and s["status"] != "live":
        await ensure_media_path(s)       # private test preview (converts browser codecs if needed)
    if s["status"] == "live":
        if ready:
            await _start_targets(s)      # restart destinations and start a new recording part
        else:
            await manager.stop(s["id"])  # inputs ended; they resume when the feed returns
            for (sid, t), r in manager.relays.items():
                if sid == s["id"]:
                    r.state = "waiting"


async def on_relay_change(session_id: str, target: str, state: str, error: str | None):
    if not target.startswith("dest:") or state not in ("live", "failed"):
        return
    s = await db.broadcast_sessions.find_one({"id": session_id}, {"_id": 0})
    if s and s["status"] == "live":
        d = next((x for x in s["destinations"] if f"dest:{x['id']}" == target), {})
        await _event(s, "destination.live" if state == "live" else "destination.failed",
                     destination_id=d.get("id"), platform=d.get("platform"), error=error)


# ---------------------------------------------------------------- HLS for viewers and private preview
@media_router.get("/media/hls/{rest:path}", include_in_schema=False)
async def hls_proxy(rest: str):
    parts = rest.split("/")
    if parts[0] == "t" and len(parts) >= 4:            # private preview: /media/hls/t/<session>.<sig>/<ingest>/<file>
        token, ingest_id, file = parts[1], parts[2], "/".join(parts[3:])
        sid, _, sig = token.partition(".")
        if not verify(sid + ingest_id, sig):
            raise HTTPException(403, "This preview link isn't valid")
        s = await db.broadcast_sessions.find_one({"id": sid, "ingest_id": ingest_id, "status": {"$in": list(ACTIVE)}})
    else:                                              # public: /media/hls/<ingest>/<file>
        ingest_id, file = parts[0], "/".join(parts[1:])
        s = await db.broadcast_sessions.find_one({"ingest_id": ingest_id, "status": "live", "visibility": "public"})
    if not s:
        raise HTTPException(404, "This stream isn't live")
    if not re.fullmatch(r"[\w.\-/]+", file) or ".." in file:
        raise HTTPException(400)
    url = f"{config.MEDIA_HLS_URL}/{s.get('media_path') or 'live/' + ingest_id}/{file}"
    client = httpx.AsyncClient(timeout=20, auth=(INTERNAL_USER, config.MEDIA_INTERNAL_SECRET))
    try:
        req = client.build_request("GET", url)
        r = await client.send(req, stream=True)
    except httpx.HTTPError:
        await client.aclose()
        raise HTTPException(502, "The media server isn't responding")
    headers = {"Cache-Control": "no-cache" if file.endswith(".m3u8") else "max-age=60"}

    async def body():
        try:
            async for chunk in r.aiter_raw():
                yield chunk
        finally:
            await r.aclose(); await client.aclose()
    return StreamingResponse(body(), status_code=r.status_code, media_type=r.headers.get("content-type"), headers=headers)
