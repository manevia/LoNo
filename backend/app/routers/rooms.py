"""Live Control Room: a producer runs a newscast/sports/event production with an
anchor and field contributors, and sends ONE continuous program into a
broadcast session (which goes to LoNo and the selected social destinations).

Where things happen:
- Contributors publish their camera/mic (WebRTC via WHIP, or an external encoder
  for field crews) to private paths room/<room>/c/<contributor>.
- The producer's Control Room receives every feed (WHEP), composites the program
  (anchor, reporter, split-screen, clip, standby) and publishes it to the
  session's ingest. Switching happens inside that program, so the broadcast never
  restarts.
- The producer also publishes each contributor's audio return (program minus
  their own mic, plus talkback) to room/<room>/ret/<contributor>.
- This API holds the room state (contributors, cues, scenes): the Control Room
  renders it, contributors' pages show their status from it, and the Creator API
  can drive it."""
import asyncio
import re
import secrets
from datetime import timedelta
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import config
from ..audit import audit
from ..broadcast import media
from ..broadcast.relays import manager
from ..broadcast.secrets_box import decrypt, encrypt, hash_key, hint
from ..db import db
from ..security import get_user
from ..util import now, now_iso

router = APIRouter(tags=["control room"])
INTERNAL = "lono-internal"
STATES = ("invited", "waiting", "cued", "on_air", "left", "removed")
SCENES = ("single", "split", "clip", "standby")


def _rid() -> str:
    return "r" + secrets.token_hex(5)


def _cid() -> str:
    return "c" + secrets.token_hex(5)


def _require_media():
    if not config.MEDIA_ENABLED:
        raise HTTPException(503, "Live broadcasting is off on this server (see docs/BROADCAST.md).")


async def _event(room: dict, type_: str, **details):
    ev = {"id": secrets.token_hex(8), "room_id": room["id"], "session_id": room.get("session_id"), "owner_id": room["owner_id"],
          "type": type_, "at": now_iso(), "details": details}
    await db.room_events.insert_one(dict(ev))
    from ..broadcast import webhooks
    await webhooks.dispatch(ev)


async def _room(room_id: str, user) -> dict:
    r = await db.rooms.find_one({"id": room_id, "owner_id": user["id"]}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Control room not found")
    return r


def _contributor_view(c: dict, feed: dict | None = None) -> dict:
    out = {k: v for k, v in c.items() if k not in ("_id", "token_hash", "key_enc")}
    out["connected"] = bool(feed and feed.get("ready"))
    out["tracks"] = (feed or {}).get("tracks", [])
    out["expired"] = c["expires_at"] < now_iso() and c["state"] == "invited"
    return out


async def room_view(r: dict) -> dict:
    contributors = await db.contributors.find({"room_id": r["id"], "state": {"$ne": "removed"}}, {"_id": 0}).sort("created_at", 1).to_list(50)
    views = []
    for c in contributors:
        feed = await media.path_info(f"room/{r['id']}/c/{c['id']}") if config.MEDIA_ENABLED else None
        views.append(_contributor_view(c, feed))
    session = await db.broadcast_sessions.find_one({"id": r.get("session_id")}, {"_id": 0, "id": 1, "status": 1, "visibility": 1, "title": 1}) if r.get("session_id") else None
    return {**r, "contributors": views, "session": session}


# ------------------------------------------------------------------ rooms
class RoomIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    kind: Literal["news", "sports", "protest", "worship", "community", "other"] = "news"
    standby_text: str = Field(default="We'll be right back", max_length=80)


@router.post("/rooms")
async def create_room(body: RoomIn, user=Depends(get_user)):
    _require_media()
    r = {"id": _rid(), "owner_id": user["id"], "title": body.title.strip(), "kind": body.kind,
         "standby_text": body.standby_text, "session_id": None, "created_at": now_iso(),
         "program": {"scene": "standby", "sources": [], "clip_url": None},
         "preview": {"scene": "standby", "sources": [], "clip_url": None},
         "fallback": "anchor"}
    await db.rooms.insert_one(dict(r))
    await audit("control_room_created", user, target=r["id"])
    return await room_view(r)


@router.get("/rooms")
async def list_rooms(user=Depends(get_user)):
    return await db.rooms.find({"owner_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.get("/rooms/{room_id}")
async def get_room(room_id: str, user=Depends(get_user)):
    return await room_view(await _room(room_id, user))


@router.get("/rooms/{room_id}/events")
async def room_events(room_id: str, user=Depends(get_user)):
    await _room(room_id, user)
    return await db.room_events.find({"room_id": room_id}, {"_id": 0}).sort("at", -1).to_list(200)


class AttachIn(BaseModel):
    session_id: str | None


@router.put("/rooms/{room_id}/session")
async def attach_session(room_id: str, body: AttachIn, user=Depends(get_user)):
    """The broadcast session the program feeds (test or live)."""
    r = await _room(room_id, user)
    if body.session_id:
        s = await db.broadcast_sessions.find_one({"id": body.session_id, "owner_id": user["id"]})
        if not s:
            raise HTTPException(404, "Broadcast session not found")
    await db.rooms.update_one({"id": r["id"]}, {"$set": {"session_id": body.session_id}})
    return await room_view(await _room(room_id, user))


# ------------------------------------------------------------------ invitations
class InviteIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    role: Literal["anchor", "reporter", "guest", "crew"] = "reporter"
    type: Literal["browser", "encoder"] = "browser"
    location: str = Field(default="", max_length=80)
    show_location: bool = False
    expires_in_minutes: int = Field(default=240, ge=5, le=60 * 24 * 7)


@router.post("/rooms/{room_id}/invites")
async def invite(room_id: str, body: InviteIn, request: Request, user=Depends(get_user)):
    _require_media()
    r = await _room(room_id, user)
    token = secrets.token_urlsafe(32)          # sent once; only its hash is stored
    key = "ck_" + secrets.token_urlsafe(20)    # publishing key for this contributor's feed
    c = {"id": _cid(), "room_id": r["id"], "owner_id": user["id"], "name": body.name.strip(), "role": body.role,
         "type": body.type, "location": body.location.strip(), "show_location": body.show_location,
         "token_hash": hash_key(token), "token_hint": token[-4:], "key_enc": encrypt(key),
         "expires_at": (now() + timedelta(minutes=body.expires_in_minutes)).isoformat(),
         "state": "invited", "cue": None, "muted": False, "audio_only": False,
         "created_at": now_iso(), "joined_at": None, "last_seen": None}
    await db.contributors.insert_one(dict(c))
    await audit("contributor_invited", user, target=c["id"], details={"room": r["id"], "role": body.role, "type": body.type})
    out = {"contributor": _contributor_view(c), "join_path": f"/join/{token}",
           "expires_at": c["expires_at"]}
    if body.type == "encoder":
        out["encoder"] = {
            "rtmp": {"server": config.INGEST_RTMP_URL.rsplit("/live", 1)[0] + f"/room/{r['id']}/c",
                     "stream_key": f"{c['id']}?user={c['id']}&pass={key}"},
            "srt": {"url": f"{config.INGEST_SRT_URL}?streamid=publish:room/{r['id']}/c/{c['id']}:{c['id']}:{key}"},
        }
    return out


class ContributorPatch(BaseModel):
    action: Literal["cue", "uncue", "mute", "unmute", "remove", "show_location", "hide_location"]
    message: str = Field(default="", max_length=140)


@router.post("/rooms/{room_id}/contributors/{cid}")
async def contributor_action(room_id: str, cid: str, body: ContributorPatch, user=Depends(get_user)):
    r = await _room(room_id, user)
    c = await db.contributors.find_one({"id": cid, "room_id": r["id"]})
    if not c or c["state"] == "removed":
        raise HTTPException(404, "Contributor not found")
    changes = {
        "cue": {"cue": body.message or "Stand by: you're next", "state": "cued" if c["state"] != "on_air" else "on_air"},
        "uncue": {"cue": None, "state": "waiting" if c["state"] == "cued" else c["state"]},
        "mute": {"muted": True}, "unmute": {"muted": False},
        "show_location": {"show_location": True}, "hide_location": {"show_location": False},
        "remove": {"state": "removed", "cue": None},
    }[body.action]
    await db.contributors.update_one({"id": cid}, {"$set": changes})
    if body.action == "remove":
        await _kick(r["id"], cid)
        for k in ("program", "preview"):
            if cid in r[k]["sources"]:
                await _set_scene(r, k, {"scene": "standby", "sources": [], "clip_url": None}, reason="removed")
        await audit("contributor_removed", user, target=cid)
    await _event(r, f"contributor.{body.action}", contributor_id=cid, name=c["name"])
    return await room_view(await _room(room_id, user))


async def _kick(room_id: str, cid: str):
    """Disconnect a removed contributor from the media server."""
    try:
        async with httpx.AsyncClient(timeout=3) as hc:
            lst = (await hc.get(f"{config.MEDIA_API_URL}/v3/webrtcsessions/list")).json().get("items", [])
            for s in lst:
                if s.get("path") == f"room/{room_id}/c/{cid}":
                    await hc.post(f"{config.MEDIA_API_URL}/v3/webrtcsessions/kick/{s['id']}")
    except (httpx.HTTPError, ValueError):
        pass


# ------------------------------------------------------------------ scenes
class SceneIn(BaseModel):
    scene: Literal["single", "split", "clip", "standby"]
    sources: list[str] = Field(default_factory=list, max_length=4)   # contributor ids, or "local" (producer's camera)
    clip_url: str | None = None


async def _set_scene(r: dict, which: str, scene: dict, reason: str = "producer"):
    await db.rooms.update_one({"id": r["id"]}, {"$set": {which: scene}})
    r[which] = scene
    if which == "program":
        on_air = set(scene["sources"])
        # contributors' on-air indicator follows the program
        async for c in db.contributors.find({"room_id": r["id"], "state": {"$in": ["waiting", "cued", "on_air"]}}):
            want = "on_air" if c["id"] in on_air else ("cued" if c.get("cue") else "waiting")
            if c["state"] != want:
                await db.contributors.update_one({"id": c["id"]}, {"$set": {"state": want, **({"cue": None} if want == "on_air" else {})}})
        await _event(r, "scene.changed", scene=scene["scene"], sources=scene["sources"], reason=reason)


def _validate(scene: SceneIn):
    need = {"single": 1, "split": 2, "clip": 0, "standby": 0}[scene.scene]
    if len(scene.sources) < need:
        raise HTTPException(422, f"A {scene.scene} scene needs {need} source(s)")
    if scene.scene == "clip" and not (scene.clip_url or "").startswith("/api/files/"):
        raise HTTPException(422, "Clips must be media uploaded to LoNo")


@router.put("/rooms/{room_id}/preview")
async def set_preview(room_id: str, body: SceneIn, user=Depends(get_user)):
    r = await _room(room_id, user)
    _validate(body)
    await _set_scene(r, "preview", body.model_dump())
    return await room_view(r)


@router.post("/rooms/{room_id}/take")
async def take(room_id: str, user=Depends(get_user)):
    """Put Preview on air (the program continues; only its content changes)."""
    r = await _room(room_id, user)
    await _set_scene(r, "program", dict(r["preview"]), reason="take")
    return await room_view(r)


@router.put("/rooms/{room_id}/program")
async def set_program(room_id: str, body: SceneIn, user=Depends(get_user)):
    """Cut straight to a scene (also used for automatic fallback when a feed drops)."""
    r = await _room(room_id, user)
    _validate(body)
    await _set_scene(r, "program", body.model_dump(), reason=body.scene)
    return await room_view(r)


class FallbackIn(BaseModel):
    reason: str = Field(default="feed_lost", max_length=40)
    contributor_id: str | None = None


@router.post("/rooms/{room_id}/fallback")
async def fallback(room_id: str, body: FallbackIn, user=Depends(get_user)):
    """An on-air feed dropped: return to the anchor if connected, else standby."""
    r = await _room(room_id, user)
    anchor = await db.contributors.find_one({"room_id": r["id"], "role": "anchor", "state": {"$in": ["waiting", "cued", "on_air"]}})
    anchor_ok = anchor and (await media.path_info(f"room/{r['id']}/c/{anchor['id']}") or {}).get("ready")
    scene = {"scene": "single", "sources": [anchor["id"]], "clip_url": None} if anchor_ok and anchor["id"] != body.contributor_id \
        else {"scene": "standby", "sources": [], "clip_url": None}
    await _set_scene(r, "program", scene, reason=f"fallback:{body.reason}")
    return await room_view(r)


# ------------------------------------------------------------------ media signalling (producer)
async def _whep(path: str, offer: str) -> Response:
    try:
        async with httpx.AsyncClient(timeout=15, auth=(INTERNAL, config.MEDIA_INTERNAL_SECRET)) as hc:
            r = await hc.post(f"{config.MEDIA_WEBRTC_URL}/{path}/whep", content=offer, headers={"Content-Type": "application/sdp"})
    except httpx.HTTPError:
        raise HTTPException(502, "The media server isn't responding")
    if r.status_code == 404:
        raise HTTPException(404, "That feed isn't connected")
    if r.status_code not in (200, 201):
        raise HTTPException(502, f"The media server refused ({r.status_code})")
    return Response(r.text, status_code=201, media_type="application/sdp")


async def _whip(path: str, offer: str, user: str, password: str) -> Response:
    try:
        async with httpx.AsyncClient(timeout=15, auth=(user, password)) as hc:
            r = await hc.post(f"{config.MEDIA_WEBRTC_URL}/{path}/whip", content=offer, headers={"Content-Type": "application/sdp"})
    except httpx.HTTPError:
        raise HTTPException(502, "The media server isn't responding")
    if r.status_code not in (200, 201):
        raise HTTPException(502, f"The media server refused the stream ({r.status_code})")
    return Response(r.text, status_code=201, media_type="application/sdp")


async def _sdp(request: Request) -> str:
    offer = (await request.body()).decode(errors="ignore")
    if not offer.startswith("v=0"):
        raise HTTPException(422, "Expected an SDP offer")
    return offer


@router.post("/rooms/{room_id}/sources/{cid}/whep")
async def watch_source(room_id: str, cid: str, request: Request, user=Depends(get_user)):
    r = await _room(room_id, user)
    c = await db.contributors.find_one({"id": cid, "room_id": r["id"], "state": {"$ne": "removed"}})
    if not c:
        raise HTTPException(404, "Contributor not found")
    # encoder feeds carry AAC, which WebRTC can't play: read the converted copy
    path = f"room/{r['id']}/{'cw' if c['type'] == 'encoder' else 'c'}/{cid}"
    return await _whep(path, await _sdp(request))


@router.post("/rooms/{room_id}/returns/{cid}/whip")
async def publish_return(room_id: str, cid: str, request: Request, user=Depends(get_user)):
    r = await _room(room_id, user)
    if not await db.contributors.find_one({"id": cid, "room_id": r["id"]}):
        raise HTTPException(404, "Contributor not found")
    return await _whip(f"room/{r['id']}/ret/{cid}", await _sdp(request), INTERNAL, config.MEDIA_INTERNAL_SECRET)


# ------------------------------------------------------------------ contributors (invitation link)
async def _by_token(token: str) -> tuple[dict, dict]:
    c = await db.contributors.find_one({"token_hash": hash_key(token)}, {"_id": 0})
    if not c or c["state"] == "removed":
        raise HTTPException(404, "This invitation isn't valid. Ask the producer for a new link.")
    if c["expires_at"] < now_iso():
        raise HTTPException(410, "This invitation has expired. Ask the producer for a new link.")
    r = await db.rooms.find_one({"id": c["room_id"]}, {"_id": 0})
    return c, r


@router.get("/join/{token}")
async def join_info(token: str):
    c, r = await _by_token(token)
    await db.contributors.update_one({"id": c["id"]}, {"$set": {"last_seen": now_iso()}})
    on_air = c["id"] in (r["program"]["sources"] or [])
    return {"room": {"title": r["title"], "kind": r["kind"]}, "contributor": {
        "id": c["id"], "name": c["name"], "role": c["role"], "type": c["type"], "location": c["location"],
        "show_location": c["show_location"], "state": c["state"], "cue": c.get("cue"), "muted": c["muted"],
        "audio_only": c["audio_only"], "expires_at": c["expires_at"]}, "on_air": on_air,
        "live": bool(r.get("session_id") and await db.broadcast_sessions.find_one({"id": r["session_id"], "status": "live"}))}


@router.post("/join/{token}/ready")
async def join_ready(token: str):
    """Enter the private waiting area."""
    c, r = await _by_token(token)
    if c["state"] in ("invited", "left"):
        await db.contributors.update_one({"id": c["id"]}, {"$set": {"state": "waiting", "joined_at": c.get("joined_at") or now_iso()}})
        await _event(r, "contributor.joined", contributor_id=c["id"], name=c["name"])
    return {"ok": True}


class AudioOnlyIn(BaseModel):
    on: bool


@router.post("/join/{token}/audio-only")
async def join_audio_only(token: str, body: AudioOnlyIn):
    c, r = await _by_token(token)
    await db.contributors.update_one({"id": c["id"]}, {"$set": {"audio_only": body.on}})
    await _event(r, "contributor.audio_only" if body.on else "contributor.video_restored", contributor_id=c["id"], name=c["name"])
    return {"ok": True}


@router.post("/join/{token}/leave")
async def join_leave(token: str):
    c, r = await _by_token(token)
    await db.contributors.update_one({"id": c["id"]}, {"$set": {"state": "left"}})
    await _event(r, "contributor.left", contributor_id=c["id"], name=c["name"])
    return {"ok": True}


@router.post("/join/{token}/whip")
async def join_publish(token: str, request: Request):
    c, r = await _by_token(token)
    if c["type"] != "browser":
        raise HTTPException(409, "This invitation is for an external encoder")
    return await _whip(f"room/{r['id']}/c/{c['id']}", await _sdp(request), c["id"], decrypt(c["key_enc"]))


@router.post("/join/{token}/return/whep")
async def join_return(token: str, request: Request):
    """The contributor's private audio return (program minus their own mic)."""
    c, r = await _by_token(token)
    return await _whep(f"room/{r['id']}/ret/{c['id']}", await _sdp(request))


# ------------------------------------------------------------------ media server hooks
async def mtx_publish_allowed(path: str, user: str, password: str) -> bool:
    m = re.fullmatch(r"room/(r[0-9a-f]{10})/c/(c[0-9a-f]{10})", path)
    if not m:
        return False
    c = await db.contributors.find_one({"id": m.group(2), "room_id": m.group(1)})
    if not c or c["state"] == "removed" or c["expires_at"] < now_iso() or user != c["id"]:
        return False
    return secrets.compare_digest(password or "", decrypt(c["key_enc"]))


async def on_contributor_feed(path: str, ready: bool):
    """Contributor connected/disconnected. Encoder feeds get a WebRTC-playable copy."""
    m = re.fullmatch(r"room/(r[0-9a-f]{10})/c/(c[0-9a-f]{10})", path)
    if not m:
        return
    c = await db.contributors.find_one({"id": m.group(2)}, {"_id": 0})
    r = await db.rooms.find_one({"id": m.group(1)}, {"_id": 0})
    if not c or not r:
        return
    await _event(r, "source.connected" if ready else "source.disconnected", contributor_id=c["id"], name=c["name"],
                 on_air=c["id"] in r["program"]["sources"])
    if c["type"] == "encoder":
        if ready:
            auth = f"{INTERNAL}:{config.MEDIA_INTERNAL_SECRET}@"
            base = config.MEDIA_RTSP_INTERNAL.replace("rtsp://", "rtsp://" + auth)
            await manager.start(f"room:{r['id']}", f"cw:{c['id']}", [
                "-hide_banner", "-nostats", "-loglevel", "warning", "-progress", "pipe:1", "-rtsp_transport", "tcp",
                "-i", f"{base}/room/{r['id']}/c/{c['id']}", "-c:v", "copy", "-c:a", "libopus", "-b:a", "96k", "-ar", "48000",
                "-f", "rtsp", "-rtsp_transport", "tcp", f"{base}/room/{r['id']}/cw/{c['id']}"])
            if c["state"] in ("invited", "left"):
                await db.contributors.update_one({"id": c["id"]}, {"$set": {"state": "waiting", "joined_at": now_iso()}})
        else:
            await manager.stop(f"room:{r['id']}", f"cw:{c['id']}")
