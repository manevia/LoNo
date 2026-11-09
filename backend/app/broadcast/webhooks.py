"""Signed webhooks for the Creator API.

Every broadcast/room event is offered to the owner's integrations that have a
webhook URL and subscribe to that event type. Delivery is asynchronous with
retries (after 2 s, 10 s, 30 s). Each request carries:

  LoNo-Event-Id:  the event id (use it to ignore duplicates)
  LoNo-Event:     the event type
  LoNo-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>" with the webhook secret>

Payloads never include stream keys, invitation tokens or social account keys."""
import asyncio
import hashlib
import hmac
import json
import logging
import time

import httpx

from ..db import db
from ..util import now_iso, spawn, uid
from .secrets_box import decrypt

log = logging.getLogger("lono.webhooks")
RETRY_DELAYS = (2, 10, 30)
TIMEOUT = 10
SENSITIVE = {"stream_key", "key", "token", "password", "secret", "join_path"}


def sign(secret: str, timestamp: int, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def verify(secret: str, header: str, body: bytes, tolerance: int = 300) -> bool:
    """Reference verifier (the same logic integrators use)."""
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        t = int(parts["t"])
    except (KeyError, ValueError):
        return False
    if abs(time.time() - t) > tolerance:
        return False
    return hmac.compare_digest(sign(secret, t, body), parts.get("v1", ""))


def _clean(details: dict) -> dict:
    return {k: v for k, v in (details or {}).items() if k not in SENSITIVE}


async def dispatch(event: dict):
    """Called for every broadcast/room event. Never raises."""
    try:
        integrations = await db.integrations.find(
            {"owner_id": event["owner_id"], "revoked_at": None, "webhook_url": {"$nin": [None, ""]}}, {"_id": 0}).to_list(50)
    except Exception:
        return
    payload = {"id": event["id"], "type": event["type"], "created_at": event["at"], "data": {
        "session_id": event.get("session_id"), "room_id": event.get("room_id"), **_clean(event.get("details"))}}
    for integ in integrations:
        subs = integ.get("webhook_events") or ["*"]
        if "*" not in subs and event["type"] not in subs:
            continue
        spawn(_deliver(integ, payload))


async def _deliver(integ: dict, payload: dict, attempt_delays=None):
    if attempt_delays is None:
        attempt_delays = RETRY_DELAYS
    body = json.dumps(payload, separators=(",", ":")).encode()
    secret = decrypt(integ["webhook_secret_enc"])
    record = {"id": uid(), "integration_id": integ["id"], "event_id": payload["id"], "type": payload["type"],
              "url": integ["webhook_url"], "attempts": [], "status": "pending", "created_at": now_iso()}
    await db.webhook_deliveries.insert_one(dict(record))
    for attempt in range(len(attempt_delays) + 1):
        t = int(time.time())
        headers = {"Content-Type": "application/json", "User-Agent": "LoNo-Webhooks/1",
                   "LoNo-Event-Id": payload["id"], "LoNo-Event": payload["type"], "LoNo-Signature": f"t={t},v1={sign(secret, t, body)}"}
        status, error = None, None
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as hc:
                r = await hc.post(integ["webhook_url"], content=body, headers=headers)
            status = r.status_code
        except httpx.HTTPError as e:
            error = type(e).__name__
        ok = status is not None and 200 <= status < 300
        await db.webhook_deliveries.update_one({"id": record["id"]}, {"$push": {"attempts": {"at": now_iso(), "status": status, "error": error}},
                                                                      "$set": {"status": "delivered" if ok else "retrying"}})
        if ok:
            return True
        if attempt < len(attempt_delays):
            await asyncio.sleep(attempt_delays[attempt])
    await db.webhook_deliveries.update_one({"id": record["id"]}, {"$set": {"status": "failed"}})
    log.warning("webhook %s to integration %s failed after retries", payload["type"], integ["id"])
    return False
