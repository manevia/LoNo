"""Creator API v1: credentials, scopes, test environment, idempotency, rate limits,
webhook URL safety and signed delivery (media server faked)."""
import asyncio
import json

import httpx
import pytest

from app import config
from app.broadcast import media, webhooks
from app.broadcast.relays import manager
from app.routers import creator_api
from test_course_builder import make_user

ALL = list(creator_api.SCOPES)


@pytest.fixture
def media_on(monkeypatch):
    monkeypatch.setattr(config, "MEDIA_ENABLED", True)

    async def info(path):
        return {"ready": True, "tracks": ["H264", "MPEG-4 Audio"], "bitrate_kbps": 3000}
    monkeypatch.setattr(media, "path_info", info)

    async def noop(*a, **k):
        return None
    monkeypatch.setattr(manager, "start", noop)
    monkeypatch.setattr(manager, "stop", noop)


def integ(client, u, scopes=ALL, env="live", **kw):
    r = client.post("/api/integrations", headers=u["h"], json={"name": "Scheduler", "scopes": scopes, "environment": env, **kw})
    assert r.status_code == 200, r.text
    d = r.json()
    return d, {"Authorization": f"Bearer {d['token']}"}


def test_token_shown_once_and_scopes_enforced(client, media_on):
    u = make_user(client)
    d, H = integ(client, u, scopes=["sessions:read"])
    assert d["token"].startswith("lk_live_") and "secret_hash" not in d
    listed = client.get("/api/integrations", headers=u["h"]).json()
    assert "token" not in listed[0] and "secret_hash" not in listed[0]
    assert client.get("/api/v1/me", headers=H).json()["creator"]["id"] == u["id"]
    assert client.get("/api/v1/sessions", headers=H).status_code == 200
    r = client.post("/api/v1/sessions", headers=H, json={"title": "x"})
    assert r.status_code == 403 and "sessions:write" in r.json()["detail"]
    assert client.get("/api/v1/ingest", headers=H).status_code == 403          # stream key needs its own scope
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer lk_live_igx.nope"}).status_code == 401
    assert client.get("/api/v1/me", headers=u["h"]).status_code == 401         # a user session isn't an API token


def test_rotate_and_revoke(client, media_on):
    u = make_user(client)
    d, H = integ(client, u)
    new = client.post(f"/api/integrations/{d['id']}/rotate", headers=u["h"]).json()["token"]
    assert client.get("/api/v1/me", headers=H).status_code == 401
    H2 = {"Authorization": f"Bearer {new}"}
    assert client.get("/api/v1/me", headers=H2).status_code == 200
    client.delete(f"/api/integrations/{d['id']}", headers=u["h"])
    assert client.get("/api/v1/me", headers=H2).status_code == 401
    other = make_user(client)
    assert client.delete(f"/api/integrations/{d['id']}", headers=other["h"]).status_code == 404


def test_session_lifecycle_idempotent_and_same_rules(client, media_on):
    u = make_user(client)
    d, H = integ(client, u)
    yt = client.post("/api/broadcast/destinations", headers=u["h"], json={"platform": "youtube", "server_url": "rtmps://a.rtmps.youtube.com/live2", "stream_key": "k-123456"}).json()
    body = {"title": "Scheduled match", "destination_ids": [yt["id"]], "scheduled_for": "2026-12-01T18:00:00+00:00"}
    s1 = client.post("/api/v1/sessions", headers={**H, "Idempotency-Key": "abc"}, json=body)
    s2 = client.post("/api/v1/sessions", headers={**H, "Idempotency-Key": "abc"}, json=body)
    assert s1.status_code == 201 and s1.json()["id"] == s2.json()["id"]          # network retry: no duplicate
    sid = s1.json()["id"]
    assert client.post("/api/v1/sessions", headers=H, json={"title": "Another"}).status_code == 409   # same one-open-session rule
    p = client.patch(f"/api/v1/sessions/{sid}", headers=H, json={"title": "Final", "record": True}).json()
    assert p["title"] == "Final" and p["record"] is True
    a = client.post(f"/api/v1/sessions/{sid}/start", headers=H).json()
    b = client.post(f"/api/v1/sessions/{sid}/start", headers=H).json()                      # retried start
    assert a["status"] == b["status"] == "live" and a["content_id"] == b["content_id"]
    h = client.get(f"/api/v1/sessions/{sid}/health", headers=H).json()
    assert h["feed"]["ready"] and h["destinations"][0]["platform"] == "youtube" and "k-123456" not in json.dumps(h)
    assert client.patch(f"/api/v1/sessions/{sid}", headers=H, json={"title": "Too late"}).status_code == 409
    x = client.post(f"/api/v1/sessions/{sid}/stop", headers=H).json()
    y = client.post(f"/api/v1/sessions/{sid}/stop", headers=H).json()                       # retried stop
    assert x["status"] == y["status"] == "ended"
    other = make_user(client)
    _, H3 = integ(client, other)
    assert client.get(f"/api/v1/sessions/{sid}", headers=H3).status_code == 404            # other creators can't see it
    log = client.get("/api/admin/audit", headers=u["h"])                                   # (admin only; just ensure no crash)
    assert log.status_code in (200, 403)


def test_test_environment_is_private(client, media_on):
    u = make_user(client)
    d, H = integ(client, u, env="test")
    assert d["token"].startswith("lk_test_")
    s = client.post("/api/v1/sessions", headers=H, json={"title": "Sandbox", "record": True}).json()
    assert s["visibility"] == "test" and s["record"] is False
    assert client.post(f"/api/v1/sessions/{s['id']}/start", headers=H).status_code == 409


def test_rate_limit(client, media_on, monkeypatch):
    u = make_user(client)
    _, H = integ(client, u)
    monkeypatch.setattr(creator_api, "limiter", creator_api.RateLimiter(3, 60, "slow down"))
    codes = [client.get("/api/v1/me", headers=H).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_webhook_url_must_be_public(client, media_on, monkeypatch):
    u = make_user(client)
    for bad in ("http://example.com/hook", "https://127.0.0.1/hook", "https://10.0.0.5/x", "https://169.254.169.254/latest", "ftp://x/y"):
        r = client.post("/api/integrations", headers=u["h"], json={"name": "x", "scopes": ["sessions:read"], "webhook_url": bad})
        assert r.status_code == 422, bad
    assert client.post("/api/integrations", headers=u["h"], json={"name": "x", "scopes": ["nope"]}).status_code == 422


def test_signed_webhooks_with_retry(client, media_on, monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOW_PRIVATE", True)
    got, calls = [], {"n": 0}

    def handler(request: httpx.Request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500)                       # first attempt fails → retried
        got.append(request)
        return httpx.Response(200)
    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(webhooks.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))
    monkeypatch.setattr(webhooks, "RETRY_DELAYS", (0.01, 0.01, 0.01))
    u = make_user(client)
    d, H = integ(client, u, webhook_url="http://localhost:9/hook", webhook_events=["broadcast.started", "broadcast.ended"])
    s = client.post("/api/v1/sessions", headers=H, json={"title": "Webhook show"}).json()
    client.post(f"/api/v1/sessions/{s['id']}/start", headers=H)
    asyncio.run(asyncio.sleep(0.3))
    client.post(f"/api/v1/sessions/{s['id']}/stop", headers=H)
    for _ in range(30):
        if len(got) >= 2:
            break
        asyncio.run(asyncio.sleep(0.05))
    types = [r.headers["LoNo-Event"] for r in got]
    assert "broadcast.started" in types and "broadcast.ended" in types
    for r in got:                                             # every delivery verifies with the secret
        assert webhooks.verify(d["webhook_secret"], r.headers["LoNo-Signature"], r.content)
        assert not webhooks.verify("whsec_wrong", r.headers["LoNo-Signature"], r.content)
        assert "stream_key" not in r.content.decode()
    dl = client.get(f"/api/integrations/{d['id']}/deliveries", headers=u["h"]).json()
    assert any(len(x["attempts"]) >= 2 and x["status"] == "delivered" for x in dl)


def test_rooms_via_api(client, media_on):
    u = make_user(client)
    _, H = integ(client, u, scopes=["rooms:read", "rooms:write", "production:control"])
    r = client.post("/api/v1/rooms", headers=H, json={"title": "Match day", "kind": "sports"}).json()
    inv = client.post(f"/api/v1/rooms/{r['id']}/invites", headers=H, json={"name": "Pitch-side", "role": "reporter"}).json()
    cid = inv["contributor"]["id"]
    client.put(f"/api/v1/rooms/{r['id']}/preview", headers=H, json={"scene": "single", "sources": [cid]})
    room = client.post(f"/api/v1/rooms/{r['id']}/take", headers=H).json()
    assert room["program"]["sources"] == [cid]
    src = client.get(f"/api/v1/rooms/{r['id']}", headers=H).json()["contributors"][0]
    assert {"state", "connected", "audio_only", "muted"} <= set(src) and "token_hash" not in src
    _, R = integ(client, u, scopes=["rooms:read"])
    assert client.post(f"/api/v1/rooms/{r['id']}/take", headers=R).status_code == 403
