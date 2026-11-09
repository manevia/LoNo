"""Control Room rules with a faked media server."""
import pytest

from app import config
from app.broadcast import media
from app.db import db
from test_course_builder import make_user


@pytest.fixture
def media_on(monkeypatch):
    monkeypatch.setattr(config, "MEDIA_ENABLED", True)
    ready = set()

    async def info(path):
        return {"ready": path in ready, "tracks": ["H264", "Opus"]}
    monkeypatch.setattr(media, "path_info", info)
    return ready


def room(client, u):
    return client.post("/api/rooms", headers=u["h"], json={"title": "Evening News"}).json()


def invite(client, u, r, **kw):
    return client.post(f"/api/rooms/{r['id']}/invites", headers=u["h"], json={"name": kw.pop("name", "Reporter"), **kw}).json()


def test_invitation_link_is_secret_and_expires(client, media_on):
    u = make_user(client); r = room(client, u)
    inv = invite(client, u, r, name="Musu", role="reporter", location="Gbarnga", expires_in_minutes=5)
    token = inv["join_path"].split("/join/")[1]
    assert "token_hash" not in str(client.get(f"/api/rooms/{r['id']}", headers=u["h"]).json())
    j = client.get(f"/api/join/{token}").json()
    assert j["contributor"]["name"] == "Musu" and j["contributor"]["state"] == "invited" and not j["on_air"]
    assert client.get("/api/join/not-a-real-token").status_code == 404
    import asyncio
    asyncio.run(db.contributors.update_one({"id": inv["contributor"]["id"]}, {"$set": {"expires_at": "2000-01-01T00:00:00+00:00"}}))
    assert client.get(f"/api/join/{token}").status_code == 410


def test_contributor_publish_auth(client, media_on):
    from app.broadcast.secrets_box import decrypt
    u = make_user(client); r = room(client, u)
    inv = invite(client, u, r)
    cid = inv["contributor"]["id"]
    import asyncio
    key = decrypt(asyncio.run(db.contributors.find_one({"id": cid}))["key_enc"])
    path = f"room/{r['id']}/c/{cid}"
    ok = client.post("/api/broadcast/mtx/auth", json={"action": "publish", "path": path, "user": cid, "password": key})
    assert ok.status_code == 204
    assert client.post("/api/broadcast/mtx/auth", json={"action": "publish", "path": path, "user": cid, "password": "x"}).status_code == 401
    other = invite(client, u, r)["contributor"]["id"]   # one contributor can't publish into another's slot
    assert client.post("/api/broadcast/mtx/auth", json={"action": "publish", "path": f"room/{r['id']}/c/{other}", "user": cid, "password": key}).status_code == 401


def test_waiting_cue_on_air_and_fallback(client, media_on):
    u = make_user(client); r = room(client, u)
    anchor = invite(client, u, r, name="Anchor", role="anchor")
    rep = invite(client, u, r, name="Field", role="reporter", location="Monrovia", show_location=True)
    a_tok, r_tok = anchor["join_path"].split("/")[-1], rep["join_path"].split("/")[-1]
    for t in (a_tok, r_tok):
        client.post(f"/api/join/{t}/ready")
    aid, rid = anchor["contributor"]["id"], rep["contributor"]["id"]
    media_on.update({f"room/{r['id']}/c/{aid}", f"room/{r['id']}/c/{rid}"})

    client.post(f"/api/rooms/{r['id']}/contributors/{rid}", headers=u["h"], json={"action": "cue", "message": "30 seconds"})
    j = client.get(f"/api/join/{r_tok}").json()
    assert j["contributor"]["state"] == "cued" and j["contributor"]["cue"] == "30 seconds"

    assert client.put(f"/api/rooms/{r['id']}/preview", headers=u["h"], json={"scene": "split", "sources": [aid]}).status_code == 422
    client.put(f"/api/rooms/{r['id']}/preview", headers=u["h"], json={"scene": "split", "sources": [aid, rid]})
    assert not client.get(f"/api/join/{r_tok}").json()["on_air"]           # preview is private
    client.post(f"/api/rooms/{r['id']}/take", headers=u["h"])
    j = client.get(f"/api/join/{r_tok}").json()
    assert j["on_air"] and j["contributor"]["state"] == "on_air" and j["contributor"]["cue"] is None

    # reporter's feed drops: producer's Control Room asks for fallback → anchor full screen
    media_on.discard(f"room/{r['id']}/c/{rid}")
    room_after = client.post(f"/api/rooms/{r['id']}/fallback", headers=u["h"], json={"contributor_id": rid}).json()
    assert room_after["program"] == {"scene": "single", "sources": [aid], "clip_url": None}
    assert not client.get(f"/api/join/{r_tok}").json()["on_air"]
    # no anchor connected either → standby
    media_on.discard(f"room/{r['id']}/c/{aid}")
    assert client.post(f"/api/rooms/{r['id']}/fallback", headers=u["h"], json={}).json()["program"]["scene"] == "standby"

    types = [e["type"] for e in client.get(f"/api/rooms/{r['id']}/events", headers=u["h"]).json()]
    assert "scene.changed" in types and "contributor.cue" in types and "contributor.joined" in types


def test_remove_and_isolation(client, media_on):
    u = make_user(client); r = room(client, u)
    rep = invite(client, u, r)
    tok, cid = rep["join_path"].split("/")[-1], rep["contributor"]["id"]
    client.put(f"/api/rooms/{r['id']}/program", headers=u["h"], json={"scene": "single", "sources": [cid]})
    client.post(f"/api/rooms/{r['id']}/contributors/{cid}", headers=u["h"], json={"action": "remove"})
    assert client.get(f"/api/join/{tok}").status_code == 404
    assert client.get(f"/api/rooms/{r['id']}", headers=u["h"]).json()["program"]["scene"] == "standby"
    stranger = make_user(client)
    assert client.get(f"/api/rooms/{r['id']}", headers=stranger["h"]).status_code == 404
    assert client.post(f"/api/rooms/{r['id']}/take", headers=stranger["h"]).status_code == 404


def test_encoder_invite_gives_ingest_details(client, media_on):
    u = make_user(client); r = room(client, u)
    inv = invite(client, u, r, name="Stadium truck", role="crew", type="encoder")
    assert inv["encoder"]["rtmp"]["server"].endswith(f"/room/{r['id']}/c")
    assert inv["encoder"]["srt"]["url"].startswith("srt://")
    tok = inv["join_path"].split("/")[-1]
    assert client.post(f"/api/join/{tok}/whip", content=b"v=0\r\n", headers={"Content-Type": "application/sdp"}).status_code == 409


def test_clip_must_be_lono_media(client, media_on):
    u = make_user(client); r = room(client, u)
    bad = client.put(f"/api/rooms/{r['id']}/preview", headers=u["h"], json={"scene": "clip", "clip_url": "https://evil.example/x.mp4"})
    assert bad.status_code == 422
