"""Object storage (Cloudflare R2 / S3) against a real S3-compatible server (moto).
Skipped when moto isn't installed (pip install "moto[server]")."""
import asyncio
import os
import socket
import threading
import time

import httpx
import pytest

moto_server = pytest.importorskip("moto.server")


@pytest.fixture(scope="module")
def s3_endpoint():
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    srv = moto_server.ThreadedMotoServer(ip_address="127.0.0.1", port=port)
    srv.start()
    yield f"http://127.0.0.1:{port}"
    srv.stop()


@pytest.fixture
def s3(monkeypatch, s3_endpoint):
    """Swap the app's storage for S3 (moto) for one test."""
    from app import config, storage as storage_mod
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test"); monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setattr(config, "S3_BUCKET", "lono-media")
    monkeypatch.setattr(config, "S3_REGION", "us-east-1")   # R2 uses "auto"; moto (like AWS) needs a real region
    monkeypatch.setattr(config, "S3_ENDPOINT_URL", s3_endpoint)
    st = storage_mod.S3Storage()
    try:
        st.s3.create_bucket(Bucket="lono-media")
    except Exception:
        pass
    import app.routers.files as files_mod, app.routers.campaigns as camp_mod
    for mod in (storage_mod, files_mod, camp_mod):
        monkeypatch.setattr(mod, "storage", st)
    return st


def user(client):
    d = client.post("/api/auth/register", json={"email": f"s3{os.urandom(3).hex()}@example.com", "password": "Passw0rd!",
                                                "name": "S3", "accept_terms": True}).json()
    return {"id": d["user"]["id"], "h": {"Authorization": f"Bearer {d['token']}"}}


def test_direct_upload_to_object_storage(client, s3):
    u = user(client)
    assert client.get("/api/storage/mode").json()["direct"] is True
    payload = os.urandom(2 * 1024 * 1024 + 7)
    up = client.post("/api/storage/upload-url", headers=u["h"], json={"filename": "Final.MP4", "content_type": "video/mp4", "size": len(payload)}).json()
    assert client.get(f"/api/files/{up['path']}").status_code == 404                 # pending: not usable yet
    put = httpx.put(up["put_url"], content=payload, headers=up["headers"])            # browser → storage, not through LoNo
    assert put.status_code == 200
    done = client.post("/api/storage/complete", headers=u["h"], json={"file_id": up["file_id"]}).json()
    assert done["size"] == len(payload) and done["url"].endswith(".mp4")
    r = client.get(done["url"], follow_redirects=False)
    assert r.status_code == 307 and "X-Amz-Signature" in r.headers["location"]
    got = httpx.get(r.headers["location"], headers={"Range": "bytes=0-1023"})
    assert got.status_code == 206 and got.content == payload[:1024]                   # seeking works from storage


def test_direct_upload_size_mismatch_and_limits(client, s3, monkeypatch):
    from app import config
    u = user(client)
    up = client.post("/api/storage/upload-url", headers=u["h"], json={"filename": "a.mp4", "content_type": "video/mp4", "size": 1000}).json()
    httpx.put(up["put_url"], content=b"x" * 2000, headers=up["headers"])
    assert client.post("/api/storage/complete", headers=u["h"], json={"file_id": up["file_id"]}).status_code == 422
    assert client.post("/api/storage/upload-url", headers=u["h"], json={"filename": "a.exe", "content_type": "application/x-msdownload", "size": 10}).status_code == 400
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 1)
    assert client.post("/api/storage/upload-url", headers=u["h"], json={"filename": "b.mp4", "content_type": "video/mp4", "size": 2 * 1024 * 1024}).status_code == 413
    other = user(client)
    assert client.post("/api/storage/complete", headers=other["h"], json={"file_id": up["file_id"]}).status_code == 404


def test_protected_replay_from_object_storage(client, s3, admin):
    """The pilot's replay protection when files live in R2: LoNo checks the pass and the
    fan's cookie, then hands out a 2-minute signed link."""
    from test_campaigns import fund_and_open, partners, _iso, _run
    from app.db import db
    from app.util import uid
    org = user(client)
    payload = os.urandom(512 * 1024)
    up = client.post("/api/storage/upload-url", headers=org["h"], json={"filename": "replay.mp4", "content_type": "video/mp4", "size": len(payload)}).json()
    httpx.put(up["put_url"], content=payload, headers=up["headers"])
    url = client.post("/api/storage/complete", headers=org["h"], json={"file_id": up["file_id"]}).json()["url"]
    replay = client.post("/api/creator/upload", headers=org["h"], json={"title": "R2 replay", "kind": "movie", "category": "Sports",
                                                                    "thumbnail_url": "/icons/icon-512.png", "stream_url": url}).json()["id"]
    preview = client.post("/api/creator/upload", headers=org["h"], json={"title": "R2 preview", "kind": "short", "category": "Sports",
                                                                     "thumbnail_url": "/icons/icon-512.png", "stream_url": "https://example.com/p.mp4"}).json()["id"]
    o, sp = partners(client, admin)
    c = client.post("/api/admin/campaigns", headers=admin["h"], json={
        "title": "R2 replay pass", "organizer_id": o["id"], "sponsor_id": sp["id"], "replay_content_id": replay,
        "earning_rule": {"content_id": preview, "min_seconds": 30, "points": 30}, "points_price": 30, "inventory_total": 5,
        "opens_at": _iso(-5), "closes_at": _iso(60), "access_days": 3,
        "financials": {"sponsor_payment": 100, "organizer_compensation": 50, "lono_fee": 50}}).json()
    fund_and_open(client, admin, c)                                    # includes the server-side playback check (R2 head)
    fan = user(client)
    _run(db.users.update_one({"id": fan["id"]}, {"$set": {"wallet.lono_balance": 30.0}}))
    claim = client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"]).json()["claim"]
    client.cookies.clear()
    assert client.get(url).status_code == 403                          # direct file URL
    play = client.post(f"/api/me/passes/{claim['id']}/play", headers=fan["h"])
    purl, cookie = play.json()["url"], play.cookies.get("lono_replay")
    client.cookies.clear()
    assert client.get(purl).status_code == 403                         # shared link without the fan's cookie
    r = client.get(purl, cookies={"lono_replay": cookie}, follow_redirects=False)
    assert r.status_code == 307 and "X-Amz-Expires=120" in r.headers["location"]
    assert httpx.get(r.headers["location"]).content == payload
    client.cookies.clear()
