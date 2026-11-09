"""LoNo Creator API v1 (/api/v1) and integration management (/api/integrations).

Integrations act for one creator with explicit scopes and the same rules as
Creator Studio (the handlers below call the same functions). Test-environment
credentials can only run private test sessions. Audio and video never pass
through this API: encoders and browsers send them to the ingest.

Auth:  Authorization: Bearer lk_<live|test>_<integration-id>.<secret>"""
import ipaddress
import secrets
import socket
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .. import config
from ..audit import audit
from ..broadcast import webhooks
from ..broadcast.secrets_box import encrypt, hash_key
from ..db import db
from ..ratelimit import RateLimiter
from ..security import get_user
from ..util import now_iso
from . import broadcast as bc
from . import rooms as rm

SCOPES = {
    "sessions:read": "Read broadcast sessions, their health and events",
    "sessions:write": "Create and update broadcast sessions",
    "broadcast:control": "Start and stop broadcasts; retry destinations",
    "ingest:read": "Read ingest URLs and the stream key",
    "destinations:read": "List connected destinations (never their keys)",
    "recordings:read": "List recordings and their files",
    "rooms:read": "Read Control Rooms and source status",
    "rooms:write": "Create Control Rooms and contributor invitations",
    "production:control": "Switch preview/program, take, fallback, cue, mute and remove sources",
}
EVENTS = ["stream.connected", "stream.disconnected", "broadcast.started", "broadcast.ended", "destination.live",
          "destination.failed", "destination.reconnecting", "recording.ready", "scene.changed", "source.connected",
          "source.disconnected", "contributor.joined", "contributor.left", "contributor.cue", "contributor.remove", "ping"]

manage = APIRouter(prefix="/integrations", tags=["developer access"])
v1 = APIRouter(prefix="/v1", tags=["creator api v1"])
bearer = HTTPBearer(auto_error=False)
limiter = RateLimiter(config.API_RATE_PER_MINUTE, 60, "Rate limit reached for this integration.")


# ------------------------------------------------------------------ webhook URL safety (SSRF)
def check_webhook_url(url: str | None):
    if not url:
        return
    u = urlparse(url)
    if u.scheme not in ("https", "http") or not u.hostname:
        raise HTTPException(422, "Webhook URL must be a full http(s) address")
    if config.WEBHOOK_ALLOW_PRIVATE:
        return
    if u.scheme != "https":
        raise HTTPException(422, "Webhook URL must use https")
    try:
        addrs = {a[4][0] for a in socket.getaddrinfo(u.hostname, u.port or 443)}
    except socket.gaierror:
        raise HTTPException(422, "Webhook host can't be resolved")
    for a in addrs:
        ip = ipaddress.ip_address(a)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(422, "Webhook URL must point to a public address")


# ------------------------------------------------------------------ management (Creator Studio → Developer Access)
class IntegrationIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    scopes: list[str] = Field(min_length=1)
    environment: Literal["live", "test"] = "test"
    webhook_url: str | None = Field(default=None, max_length=500)
    webhook_events: list[str] = Field(default_factory=lambda: ["*"])


class IntegrationPatch(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    scopes: list[str] | None = None
    webhook_url: str | None = Field(default=None, max_length=500)
    webhook_events: list[str] | None = None


def _validate(scopes=None, events=None):
    if scopes is not None and (bad := [s for s in scopes if s not in SCOPES]):
        raise HTTPException(422, f"Unknown scope(s): {', '.join(bad)}")
    if events is not None and (bad := [e for e in events if e != "*" and e not in EVENTS]):
        raise HTTPException(422, f"Unknown event(s): {', '.join(bad)}")


def _view(i: dict) -> dict:
    return {k: v for k, v in i.items() if k not in ("_id", "secret_hash", "webhook_secret_enc")}


def _token(i: dict, secret: str) -> str:
    return f"lk_{i['environment']}_{i['id']}.{secret}"


@manage.get("/meta")
async def meta():
    return {"scopes": SCOPES, "events": EVENTS}


@manage.get("")
async def list_integrations(user=Depends(get_user)):
    return [_view(i) for i in await db.integrations.find({"owner_id": user["id"]}).sort("created_at", -1).to_list(50)]


@manage.post("")
async def create_integration(body: IntegrationIn, user=Depends(get_user)):
    _validate(body.scopes, body.webhook_events)
    check_webhook_url(body.webhook_url)
    secret, wh = secrets.token_urlsafe(32), "whsec_" + secrets.token_urlsafe(24)
    i = {"id": "ig" + secrets.token_hex(5), "owner_id": user["id"], "name": body.name.strip(), "scopes": sorted(set(body.scopes)),
         "environment": body.environment, "secret_hash": hash_key(secret), "secret_hint": secret[-4:],
         "webhook_url": body.webhook_url or None, "webhook_events": body.webhook_events, "webhook_secret_enc": encrypt(wh),
         "created_at": now_iso(), "last_used_at": None, "revoked_at": None}
    await db.integrations.insert_one(dict(i))
    await audit("integration_created", user, target=i["id"], details={"scopes": i["scopes"], "environment": i["environment"]})
    return {**_view(i), "token": _token(i, secret), "webhook_secret": wh,
            "note": "Copy the token and webhook secret now. LoNo stores only a hash of the token."}


async def _own_integration(iid: str, user) -> dict:
    i = await db.integrations.find_one({"id": iid, "owner_id": user["id"]})
    if not i:
        raise HTTPException(404, "Integration not found")
    return i


@manage.patch("/{iid}")
async def update_integration(iid: str, body: IntegrationPatch, user=Depends(get_user)):
    i = await _own_integration(iid, user)
    _validate(body.scopes, body.webhook_events)
    if body.webhook_url is not None:
        check_webhook_url(body.webhook_url)
    changes = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "scopes" in changes:
        changes["scopes"] = sorted(set(changes["scopes"]))
    if "webhook_url" in changes and not changes["webhook_url"]:
        changes["webhook_url"] = None
    await db.integrations.update_one({"id": i["id"]}, {"$set": changes})
    await audit("integration_updated", user, target=i["id"], details={k: v for k, v in changes.items() if k != "webhook_url"})
    return _view(await db.integrations.find_one({"id": i["id"]}))


@manage.post("/{iid}/rotate")
async def rotate_integration(iid: str, user=Depends(get_user)):
    i = await _own_integration(iid, user)
    secret = secrets.token_urlsafe(32)
    await db.integrations.update_one({"id": i["id"]}, {"$set": {"secret_hash": hash_key(secret), "secret_hint": secret[-4:]}})
    await audit("integration_token_rotated", user, target=i["id"])
    return {"token": _token(i, secret)}


@manage.post("/{iid}/webhook-secret/rotate")
async def rotate_webhook_secret(iid: str, user=Depends(get_user)):
    i = await _own_integration(iid, user)
    wh = "whsec_" + secrets.token_urlsafe(24)
    await db.integrations.update_one({"id": i["id"]}, {"$set": {"webhook_secret_enc": encrypt(wh)}})
    await audit("integration_webhook_secret_rotated", user, target=i["id"])
    return {"webhook_secret": wh}


@manage.delete("/{iid}")
async def revoke_integration(iid: str, user=Depends(get_user)):
    i = await _own_integration(iid, user)
    await db.integrations.update_one({"id": i["id"]}, {"$set": {"revoked_at": now_iso()}})
    await audit("integration_revoked", user, target=i["id"])
    return {"ok": True}


@manage.get("/{iid}/deliveries")
async def deliveries(iid: str, user=Depends(get_user)):
    await _own_integration(iid, user)
    return await db.webhook_deliveries.find({"integration_id": iid}, {"_id": 0}).sort("created_at", -1).to_list(100)


# ------------------------------------------------------------------ v1 auth
class Caller:
    def __init__(self, integration: dict, user: dict):
        self.integration, self.user = integration, user

    @property
    def test(self) -> bool:
        return self.integration["environment"] == "test"

    @property
    def actor(self) -> dict:
        return {"id": self.user["id"], "name": f"API: {self.integration['name']}"}


def need(*scopes: str):
    async def dep(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Caller:
        tok = creds.credentials if creds else ""
        if not tok.startswith("lk_") or "." not in tok:
            raise HTTPException(401, "Send an integration token: Authorization: Bearer lk_…")
        head, secret = tok.split(".", 1)
        iid = head.split("_")[-1]
        i = await db.integrations.find_one({"id": iid}, {"_id": 0})
        if not i or i.get("revoked_at") or not secrets.compare_digest(hash_key(secret), i["secret_hash"]):
            raise HTTPException(401, "Invalid or revoked integration token")
        limiter.check(iid)
        limiter.hit(iid)
        if missing := [s for s in scopes if s not in i["scopes"]]:
            raise HTTPException(403, f"This integration lacks the scope(s): {', '.join(missing)}")
        user = await db.users.find_one({"id": i["owner_id"]}, {"_id": 0, "password_hash": 0})
        if not user or user.get("suspended"):
            raise HTTPException(403, "The account behind this integration is not active")
        await db.integrations.update_one({"id": iid}, {"$set": {"last_used_at": now_iso()}})
        return Caller(i, user)
    return dep


# ------------------------------------------------------------------ v1: identity, ingest, destinations
@v1.get("/me")
async def me(c: Caller = Depends(need())):
    return {"integration": {"id": c.integration["id"], "name": c.integration["name"], "scopes": c.integration["scopes"],
                            "environment": c.integration["environment"]}, "creator": {"id": c.user["id"], "name": c.user["name"]}}


@v1.get("/ingest")
async def ingest(c: Caller = Depends(need("ingest:read"))):
    return bc._ingest_view(await bc._ingest_for(c.user))


@v1.get("/destinations")
async def destinations(c: Caller = Depends(need("destinations:read"))):
    return await bc.list_destinations(user=c.user)


# ------------------------------------------------------------------ v1: sessions
class SessionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=60)
    destination_ids: list[str] | None = None
    record: bool | None = None
    scheduled_for: str | None = None


def _public_session(view: dict) -> dict:
    return {k: v for k, v in view.items() if k not in ("owner_id",)}


@v1.get("/sessions")
async def sessions(c: Caller = Depends(need("sessions:read"))):
    return await bc.list_sessions(user=c.user)


@v1.post("/sessions", status_code=201)
async def create_session(body: bc.SessionIn, c: Caller = Depends(need("sessions:write")),
                         idempotency_key: str | None = Header(default=None)):
    if c.test:
        body.test = True                           # test credentials: private sessions only
    s = await bc.create_session_for(c.user, body, f"api:{c.integration['id']}:{idempotency_key}" if idempotency_key else None)
    await audit("api_session_created", c.actor, target=s["id"], details={"integration": c.integration["id"]})
    return _public_session(await bc._session_view(s))


@v1.get("/sessions/{sid}")
async def get_session(sid: str, c: Caller = Depends(need("sessions:read"))):
    return _public_session(await bc._session_view(await bc._session(sid, c.user)))


@v1.patch("/sessions/{sid}")
async def update_session(sid: str, body: SessionPatch, c: Caller = Depends(need("sessions:write"))):
    s = await bc._session(sid, c.user)
    if s["status"] != "created":
        raise HTTPException(409, "Only sessions that haven't gone live can be changed")
    changes = body.model_dump(exclude_none=True)
    if "destination_ids" in changes:
        if s["visibility"] == "test":
            changes.pop("destination_ids")
        else:
            dests = []
            for did in changes.pop("destination_ids"):
                d = await db.destinations.find_one({"id": did, "owner_id": c.user["id"]})
                if not d:
                    raise HTTPException(422, "One of the destinations doesn't exist")
                dests.append({"id": d["id"], "platform": d["platform"], "name": d["name"]})
            changes["destinations"] = dests
    if "record" in changes and s["visibility"] == "test":
        changes["record"] = False
    await db.broadcast_sessions.update_one({"id": sid}, {"$set": changes})
    await audit("api_session_updated", c.actor, target=sid, details={"fields": sorted(changes)})
    return _public_session(await bc._session_view(await bc._session(sid, c.user)))


@v1.get("/sessions/{sid}/health")
async def session_health(sid: str, c: Caller = Depends(need("sessions:read"))):
    v = await bc._session_view(await bc._session(sid, c.user))
    return {"session_id": sid, "status": v["status"], "visibility": v["visibility"], "feed": v["feed"],
            "destinations": [{k: d.get(k) for k in ("id", "platform", "name", "state", "error", "attempts", "auto_retries")} for d in v["destinations"]],
            "recorder": v.get("recorder")}


@v1.post("/sessions/{sid}/start")
async def start(sid: str, c: Caller = Depends(need("broadcast:control"))):
    """Safe to retry: starting a live session again returns it unchanged."""
    if c.test:
        raise HTTPException(409, "Test credentials can't start a public broadcast. Use live credentials.")
    s = await bc.start_session_for(c.user, sid)
    await audit("api_broadcast_started", c.actor, target=sid)
    return _public_session(await bc._session_view(s))


@v1.post("/sessions/{sid}/stop")
async def stop(sid: str, c: Caller = Depends(need("broadcast:control"))):
    """Safe to retry: stopping an ended session returns it unchanged."""
    s = await bc.stop_session_for(c.user, sid)
    await audit("api_broadcast_stopped", c.actor, target=sid)
    return _public_session(await bc._session_view(s))


@v1.post("/sessions/{sid}/destinations/{did}/retry")
async def retry_destination(sid: str, did: str, c: Caller = Depends(need("broadcast:control"))):
    return await bc.retry_destination(sid, did, user=c.user)


@v1.get("/sessions/{sid}/events")
async def session_events(sid: str, c: Caller = Depends(need("sessions:read"))):
    return await bc.session_events(sid, user=c.user)


# ------------------------------------------------------------------ v1: recordings
@v1.get("/recordings")
async def recordings(c: Caller = Depends(need("recordings:read"))):
    return await bc.recordings(user=c.user)


@v1.get("/recordings/{rid}")
async def recording(rid: str, c: Caller = Depends(need("recordings:read"))):
    r = await db.recordings.find_one({"id": rid, "owner_id": c.user["id"]}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Recording not found")
    return bc.signed_download(r)


# ------------------------------------------------------------------ v1: Control Room
@v1.get("/rooms")
async def rooms(c: Caller = Depends(need("rooms:read"))):
    return await rm.list_rooms(user=c.user)


@v1.post("/rooms", status_code=201)
async def create_room(body: rm.RoomIn, c: Caller = Depends(need("rooms:write"))):
    return await rm.create_room(body, user=c.user)


@v1.get("/rooms/{room_id}")
async def room(room_id: str, c: Caller = Depends(need("rooms:read"))):
    """Includes each source's status: state (invited/waiting/cued/on_air/left), connected, tracks, audio_only, muted."""
    return await rm.get_room(room_id, user=c.user)


@v1.post("/rooms/{room_id}/invites", status_code=201)
async def invite(room_id: str, body: rm.InviteIn, request: Request, c: Caller = Depends(need("rooms:write"))):
    return await rm.invite(room_id, body, request, user=c.user)


@v1.post("/rooms/{room_id}/contributors/{cid}")
async def contributor_action(room_id: str, cid: str, body: rm.ContributorPatch, c: Caller = Depends(need("production:control"))):
    return await rm.contributor_action(room_id, cid, body, user=c.user)


@v1.put("/rooms/{room_id}/preview")
async def preview(room_id: str, body: rm.SceneIn, c: Caller = Depends(need("production:control"))):
    return await rm.set_preview(room_id, body, user=c.user)


@v1.post("/rooms/{room_id}/take")
async def take(room_id: str, c: Caller = Depends(need("production:control"))):
    return await rm.take(room_id, user=c.user)


@v1.put("/rooms/{room_id}/program")
async def program(room_id: str, body: rm.SceneIn, c: Caller = Depends(need("production:control"))):
    return await rm.set_program(room_id, body, user=c.user)


@v1.post("/rooms/{room_id}/fallback")
async def fallback(room_id: str, body: rm.FallbackIn, c: Caller = Depends(need("production:control"))):
    return await rm.fallback(room_id, body, user=c.user)


# ------------------------------------------------------------------ v1: webhooks
@v1.post("/webhooks/test")
async def webhook_test(c: Caller = Depends(need())):
    """Send a signed 'ping' to this integration's webhook URL."""
    if not c.integration.get("webhook_url"):
        raise HTTPException(409, "This integration has no webhook URL")
    ok = await webhooks._deliver(c.integration, {"id": "evt_" + secrets.token_hex(8), "type": "ping", "created_at": now_iso(),
                                                 "data": {"integration_id": c.integration["id"]}}, attempt_delays=())
    return {"delivered": ok}
