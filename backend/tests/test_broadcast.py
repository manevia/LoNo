"""Broadcast API rules, without a media server (media and relays are faked).
The full pipeline (MediaMTX + ffmpeg + stand-in platforms) is exercised by
scripts/broadcast_integration.py; see docs/BROADCAST.md."""
import pytest

from app import config
from app.broadcast import media
from app.broadcast.relays import manager
from app.broadcast.secrets_box import redact
from app.routers import broadcast as bc
from test_course_builder import make_user


@pytest.fixture
def media_on(monkeypatch):
    monkeypatch.setattr(config, "MEDIA_ENABLED", True)
    state = {"ready": True}

    async def fake_info(path):
        return {"ready": state["ready"], "tracks": ["H264", "MPEG-4 Audio"], "has_video": True, "has_audio": True, "bitrate_kbps": 2500}
    monkeypatch.setattr(media, "path_info", fake_info)
    started = []

    async def fake_start(session_id, target_id, args, secrets=()):
        started.append((session_id, target_id, args))
    async def fake_stop(session_id, target_id=None):
        return None
    monkeypatch.setattr(manager, "start", fake_start)
    monkeypatch.setattr(manager, "stop", fake_stop)
    return {"state": state, "started": started}


def test_broadcasting_off_by_default(client):
    u = make_user(client)
    r = client.post("/api/broadcast/sessions", headers=u["h"], json={"title": "x"})
    assert r.status_code == 503


def test_ingest_key_rotation_and_auth_callback(client, media_on):
    u = make_user(client)
    ing = client.get("/api/broadcast/ingest", headers=u["h"]).json()
    key = ing["rtmp"]["stream_key"].split("key=")[1]
    path = ing["path"]
    ok = client.post("/api/broadcast/mtx/auth", json={"action": "publish", "path": path, "query": f"key={key}", "protocol": "rtmp"})
    assert ok.status_code == 204
    assert client.post("/api/broadcast/mtx/auth", json={"action": "publish", "path": path, "query": "key=nope"}).status_code == 401
    assert client.post("/api/broadcast/mtx/auth", json={"action": "read", "path": path}).status_code == 401  # viewers go through /media
    assert client.post("/api/broadcast/mtx/auth", json={"action": "publish", "path": path, "user": ing["ingest_id"], "password": key, "protocol": "srt"}).status_code == 204
    new = client.post("/api/broadcast/ingest/rotate", headers=u["h"]).json()
    assert new["rtmp"]["stream_key"] != ing["rtmp"]["stream_key"]
    assert client.post("/api/broadcast/mtx/auth", json={"action": "publish", "path": path, "query": f"key={key}"}).status_code == 401
    internal = client.post("/api/broadcast/mtx/auth", json={"action": "read", "path": path, "user": "lono-internal", "password": config.MEDIA_INTERNAL_SECRET})
    assert internal.status_code == 204


def test_destinations_validation_and_secrecy(client, media_on):
    u = make_user(client)
    assert client.post("/api/broadcast/destinations", headers=u["h"], json={"platform": "discord", "server_url": "rtmp://a/b"}).status_code == 422
    assert client.post("/api/broadcast/destinations", headers=u["h"], json={"platform": "facebook", "server_url": "rtmp://a/b"}).status_code == 422
    d = client.post("/api/broadcast/destinations", headers=u["h"], json={"platform": "youtube", "server_url": "rtmps://a.rtmps.youtube.com/live2", "stream_key": "abcd-SECRET-9999"}).json()
    assert d["key_hint"] == "…9999"
    assert "SECRET" not in client.get("/api/broadcast/destinations", headers=u["h"]).text
    other = make_user(client)
    assert client.delete(f"/api/broadcast/destinations/{d['id']}", headers=other["h"]).status_code == 404


def test_session_lifecycle(client, media_on):
    u = make_user(client)
    yt = client.post("/api/broadcast/destinations", headers=u["h"], json={"platform": "youtube", "server_url": "rtmp://a.rtmp.youtube.com/live2", "stream_key": "yt-key-1234"}).json()
    s = client.post("/api/broadcast/sessions", headers={**u["h"], "Idempotency-Key": "k1"}, json={"title": "Show", "destination_ids": [yt["id"]], "record": True}).json()
    again = client.post("/api/broadcast/sessions", headers={**u["h"], "Idempotency-Key": "k1"}, json={"title": "Other"}).json()
    assert again["id"] == s["id"]
    assert client.post("/api/broadcast/sessions", headers=u["h"], json={"title": "Second"}).status_code == 409  # one open session
    media_on["state"]["ready"] = False
    assert client.post(f"/api/broadcast/sessions/{s['id']}/start", headers=u["h"]).status_code == 409  # no feed yet
    media_on["state"]["ready"] = True
    live = client.post(f"/api/broadcast/sessions/{s['id']}/start", headers=u["h"]).json()
    assert live["status"] == "live" and live["content_id"]
    assert client.post(f"/api/broadcast/sessions/{s['id']}/start", headers=u["h"]).json()["content_id"] == live["content_id"]
    targets = {t for _, t, _ in media_on["started"]}
    assert targets == {f"dest:{yt['id']}", "recorder"}
    dest_args = next(a for _, t, a in media_on["started"] if t.startswith("dest:"))
    assert dest_args[-1] == "rtmp://a.rtmp.youtube.com/live2/yt-key-1234" and dest_args[dest_args.index("-c:v") + 1] == "copy"  # H.264/AAC passthrough
    assert any(c["id"] == live["content_id"] for c in client.get("/api/live/guide").json()["tv"])
    other = make_user(client)
    assert client.post(f"/api/broadcast/sessions/{s['id']}/stop", headers=other["h"]).status_code == 404
    end = client.post(f"/api/broadcast/sessions/{s['id']}/stop", headers=u["h"]).json()
    assert end["status"] == "ended" and client.post(f"/api/broadcast/sessions/{s['id']}/stop", headers=u["h"]).json()["status"] == "ended"
    assert not any(c["title"] == "Show" for c in client.get("/api/live/guide").json()["tv"])
    types = [e["type"] for e in client.get(f"/api/broadcast/sessions/{s['id']}/events", headers=u["h"]).json()]
    assert types[:2] == ["broadcast.started", "broadcast.ended"]


def test_test_session_is_private(client, media_on):
    u = make_user(client)
    s = client.post("/api/broadcast/sessions", headers=u["h"], json={"title": "Mic check", "test": True, "record": True}).json()
    assert s["visibility"] == "test" and s["record"] is False and s["public_url"] is None
    assert client.post(f"/api/broadcast/sessions/{s['id']}/start", headers=u["h"]).status_code == 409
    assert client.get(f"/media/hls/{s['ingest_id']}/index.m3u8").status_code == 404           # not public
    bad = s["preview_url"].replace("/t/", "/t/x").split("/t/")[0] + "/t/" + s["id"] + ".forged/" + s["ingest_id"] + "/index.m3u8"
    assert client.get(bad).status_code == 403                                                  # forged preview link


def test_redaction():
    assert redact("rtmp://x/app/sk-123456 failed", "sk-123456") == "rtmp://x/app/•••• failed"


def test_codec_args_copy_or_convert():
    assert bc._codec_args(["H264", "MPEG-4 Audio"]) == ["-c:v", "copy", "-c:a", "copy"]
    browser = bc._codec_args(["VP8", "Opus"])
    assert "libx264" in browser and "aac" in browser
    h264_opus = bc._codec_args(["H264", "Opus"])
    assert h264_opus[:2] == ["-c:v", "copy"] and "aac" in h264_opus


def test_whip_needs_a_session(client, media_on):
    u = make_user(client)
    r = client.post("/api/broadcast/whip", headers={**u["h"], "Content-Type": "application/sdp"}, content=b"v=0\r\n")
    assert r.status_code == 409


def test_relay_reconnects_only_after_being_live():
    """A destination that was live and dropped reconnects automatically (3 tries);
    one that never connected fails at once (likely a wrong URL or key)."""
    import asyncio, shutil
    from app.broadcast import relays
    if not shutil.which("ffmpeg"):
        return
    relays.BACKOFF, saved = (0.2, 0.2, 0.2), relays.BACKOFF

    async def run():
        m = relays.RelayManager()
        await m.start("s", "bad", ["-hide_banner", "-loglevel", "error", "-i", "rtmp://127.0.0.1:1/x", "-f", "null", "-"])
        await m.start("s", "drop", ["-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-re", "-f", "lavfi",
                                    "-i", "testsrc=size=160x120:rate=10", "-t", "1.2", "-f", "null", "-"])
        await asyncio.sleep(10)
        v = m.get("s")
        await m.stop_all()
        return v
    try:
        v = asyncio.run(run())
    finally:
        relays.BACKOFF = saved
    assert v["bad"]["state"] == "failed" and v["bad"]["auto_retries"] == 0
    assert v["drop"]["state"] == "failed" and v["drop"]["auto_retries"] == 3 and v["drop"]["attempts"] == 4
