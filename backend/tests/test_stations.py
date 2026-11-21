"""Permanent station and schedule integration tests; no real encoder required."""
from datetime import timedelta

from app.util import now
from test_broadcast import media_on


def test_monitoring_and_audience_access(client, user, admin):
    h = user["h"]
    sid = client.put("/api/creator/stations/live_radio", headers=h, json={"name":"Monitored radio"}).json()["id"]
    root = f"/api/creator/stations/{sid}"
    public = f"/api/stations/{sid}/audience-heartbeat"
    assert client.get(root+"/monitoring",headers=admin["h"]).status_code == 404
    assert client.post(public).status_code == 401
    assert client.post(public,headers=h).json()["ok"] is False
    assert client.get(root+"/monitoring",headers=h).json()["status"] == "off_air"
    fid = client.post("/api/storage/upload", headers=h, files={"file":("ident.mp3",b"test", "audio/mpeg")}).json()["file_id"]
    assert client.put(root+"/automation",headers=h,json={"enabled":True,"fallback_file_id":fid}).status_code == 200
    assert client.post(public,headers=h).status_code == 200
    assert client.post(public,headers=h).status_code == 200
    result = client.get(root+"/monitoring",headers=h).json()
    assert result["today_signed_in_accounts"] == 1 and result["recent_signed_in_accounts"] == 1
    assert client.get(root+"/monitoring",headers=h).json()["status"] == "media_available"


def test_playlist_clock_and_fallback():
    from app.routers.stations import playout
    t = now()
    station = {"owner_id":"owner", "kind":"live_radio", "automation_enabled":True,
               "playlist_continuous":True, "playlist_anchor":t.isoformat(), "fallback_file_id":"a",
               "playlist_items":[{"file_id":"a","title":"Music","duration":30,"kind":"programme"},
                                 {"file_id":"b","title":"Break","duration":10,"kind":"commercial"}]}
    files = {k:{"id":k,"user_id":"owner","storage_path":f"uploads/owner/{k}.mp3","content_type":"audio/mpeg"} for k in ("a","b")}
    def at(seconds):
        return playout(station,None,None,None,None,files,(t+timedelta(seconds=seconds)).isoformat())
    assert at(0)["title"] == "Music"
    assert at(30)["item_kind"] == "commercial"
    assert at(40)["title"] == "Music"
    del files["b"]
    assert at(35)["item_kind"] == "fallback"
    assert playout(station,{"content_id":"live","title":"Presenter"},"https://example.invalid/live",None,None,files,t.isoformat())["mode"] == "live"


def test_playlist_owner_and_scheduled_snapshot(client, user, admin):
    h = user["h"]
    sid = client.put("/api/creator/stations/live_radio", headers=h, json={"name":"Playlist radio"}).json()["id"]
    root = f"/api/creator/stations/{sid}"
    file_id = client.post("/api/storage/upload", headers=h, files={"file":("ident.mp3",b"test", "audio/mpeg")}).json()["file_id"]
    item = {"file_id":file_id,"title":"Ident","duration":30,"kind":"jingle"}
    playlist = {"items":[item],"continuous":True}
    assert client.put(root+"/playlist",headers=admin["h"],json=playlist).status_code == 404
    assert client.put(root+"/playlist",headers=h,json={"items":[{**item,"file_id":"missing"}],"continuous":True}).status_code == 422
    assert client.put(root+"/playlist",headers=h,json=playlist).status_code == 200
    assert client.put(root+"/automation",headers=h,json={"enabled":True}).status_code == 200
    assert client.get(f"/api/stations/{sid}").json()["playout"]["item_kind"] == "jingle"
    t = now()
    slot = {"title":"Scheduled lineup","format":"prerecorded","playlist":True,"start":(t-timedelta(seconds=1)).isoformat(),"end":(t+timedelta(hours=1)).isoformat()}
    assert client.post(root+"/programmes",headers=h,json=slot).status_code == 200
    assert client.put(root+"/playlist",headers=h,json={"items":[],"continuous":False}).status_code == 200
    assert client.get(f"/api/stations/{sid}").json()["playout"]["item_kind"] == "jingle"


def test_station_identity_schedule_and_moderation(client, user, admin):
    h = user["h"]
    path = "/api/creator/stations/live_tv"
    body = {"name": "Test TV", "category": "Education"}
    assert client.put(path, json=body).status_code == 401
    first = client.put(path, json=body, headers=h).json()
    assert first["kind"] == "live_tv" and not first["on_air"]
    sid = first["id"]
    assert client.put(path, json={**body, "name": "Renamed TV"}, headers=h).json()["id"] == sid
    radio = client.put("/api/creator/stations/live_radio", json={"name": "Test Radio"}, headers=h).json()
    assert radio["id"] != sid
    assert client.get(f"/api/stations/{sid}").json()["name"] == "Renamed TV"
    start = now() + timedelta(hours=1)
    p = {"title": "Learning Hour", "start": start.isoformat(), "end": (start + timedelta(hours=1)).isoformat()}
    ep = f"/api/creator/stations/{sid}/programmes"
    assert client.post(ep, json=p, headers=admin["h"]).status_code == 404
    listing = client.post(ep, json=p, headers=h)
    assert listing.status_code == 200, listing.text
    assert client.post(ep, json=p, headers=h).status_code == 409
    assert client.post(ep, json={**p, "end": p["start"]}, headers=h).status_code == 422
    result = client.get(f"/api/stations/{sid}").json()
    assert result["next"]["title"] == p["title"] and result["live_content_id"] is None
    assert "owner_id" not in result and "revision" not in result
    assert client.delete(f"{ep}/{listing.json()['id']}", headers=admin["h"]).status_code == 404
    assert client.delete(f"{ep}/{listing.json()['id']}", headers=h).status_code == 200
    visibility = f"/api/admin/stations/{sid}/visibility"
    assert client.post(visibility, json={"hidden": True, "reason": "test hide"}, headers=h).status_code == 403
    assert client.post(visibility, json={"hidden": True, "reason": "test hide"}, headers=admin["h"]).status_code == 200
    assert client.get(f"/api/stations/{sid}").status_code == 404
    assert client.put(path, json=body, headers=h).json()["hidden"] is True
    assert client.post(visibility, json={"hidden": False, "reason": "test restore"}, headers=admin["h"]).status_code == 200
    assert client.get(f"/api/stations/{sid}").status_code == 200


def test_station_branding_validation(client, user):
    path = "/api/creator/stations/live_tv"
    assert client.put(path, json={"name": "TV", "logo_url": "javascript:alert(1)"}, headers=user["h"]).status_code == 422
    assert client.put(path, json={"name": "TV", "logo_url": "/api/files/uploads/another/unknown.png"}, headers=user["h"]).status_code == 422


def test_recurring_schedule_atomic_conflicts(client, user, admin):
    h = user["h"]
    sid = client.put("/api/creator/stations/live_radio", headers=h, json={"name": "Recurring Radio"}).json()["id"]
    ep = f"/api/creator/stations/{sid}/programmes"
    start = now() + timedelta(hours=2)
    body = {"title": "Daily show", "start": start.isoformat(), "end": (start+timedelta(hours=1)).isoformat(), "repeat": "daily", "occurrences": 3}
    assert client.post(ep, headers=admin["h"], json=body).status_code == 404
    conflict = {"title": "Existing", "start": (start+timedelta(days=2)).isoformat(), "end": (start+timedelta(days=2,hours=1)).isoformat()}
    old = client.post(ep, headers=h, json=conflict).json()
    assert client.post(ep, headers=h, json=body).status_code == 409
    assert len(client.get(f"/api/stations/{sid}").json()["programmes"]) == 1
    assert client.delete(ep+"/"+old["id"], headers=h).status_code == 200
    result = client.post(ep, headers=h, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["occurrences_created"] == 3
    slots = client.get(f"/api/stations/{sid}").json()["programmes"]
    assert len(slots) == 3 and len({p["series_id"] for p in slots}) == 1
    assert slots[2]["start"] == conflict["start"]
    assert client.post(ep, headers=h, json={**body,"occurrences":53}).status_code == 422


def test_import_flagship_ident(client, user, admin, monkeypatch):
    from app.routers import stations
    s = client.put("/api/creator/stations/live_radio", json={"name": "Opening station"}, headers=user["h"]).json()
    sid = s["id"]
    root = f"/api/creator/stations/{sid}"
    assert client.post(root + "/starter-media", headers=user["h"]).status_code == 404
    monkeypatch.setitem(stations.STARTER_MEDIA, sid, ("LoNo_Radio_Opening_Ident.mp3", "audio/mpeg"))
    assert client.post(root + "/starter-media", headers=admin["h"]).status_code == 404
    result = client.post(root + "/starter-media", headers=user["h"])
    assert result.status_code == 200, result.text
    fid = result.json()["file_id"]
    assert client.post(root + "/starter-media", headers=user["h"]).json()["file_id"] == fid
    assert any(f["id"] == fid for f in client.get(root + "/media", headers=user["h"]).json())
    assert client.put(root + "/automation", headers=user["h"], json={"enabled": True, "fallback_file_id": fid}).status_code == 200
    assert client.get(f"/api/stations/{sid}").json()["playout"]["mode"] == "fallback"


def test_station_tracks_live_session_and_real_guide(client, user, media_on):
    h = user["h"]
    station = client.put("/api/creator/stations/live_tv", json={"name": "Network TV"}, headers=h).json()
    sid = station["id"]
    t = now()
    listing = {"title": "Live news", "start": (t - timedelta(minutes=15)).isoformat(), "end": (t + timedelta(hours=1)).isoformat()}
    assert client.post(f"/api/creator/stations/{sid}/programmes", json=listing, headers=h).status_code == 200
    session = client.post("/api/broadcast/sessions", json={"title": "News"}, headers=h).json()
    assert not client.get(f"/api/stations/{sid}").json()["on_air"]
    live = client.post(f"/api/broadcast/sessions/{session['id']}/start", headers=h).json()
    assert live["status"] == "live"
    detail = client.get(f"/api/stations/{sid}").json()
    assert detail["on_air"] and detail["live_content_id"] == live["content_id"]
    row = next(c for c in client.get("/api/live/guide").json()["tv"] if c["id"] == live["content_id"])
    assert row["station_name"] == "Network TV" and row["now"]["title"] == "Live news"
    assert client.post(f"/api/broadcast/sessions/{session['id']}/stop", headers=h).status_code == 200
    assert not client.get(f"/api/stations/{sid}").json()["on_air"]


def test_automation_schedule_fallback_live_override(client, user, media_on):
    h = user["h"]
    s = client.put("/api/creator/stations/live_tv", json={"name": "Automated TV"}, headers=h).json()
    sid = s["id"]
    root = f"/api/creator/stations/{sid}"
    media = client.post("/api/storage/upload", headers=h, files={"file": ("programme.mp4", b"test data", "video/mp4")}).json()
    fid = media["file_id"]
    assert client.get(root + "/media", headers=h).json()[0]["id"] == fid
    assert client.put(root + "/automation", headers=h, json={"enabled": True, "fallback_file_id": "unknown"}).status_code == 422
    assert client.put(root + "/automation", headers=h, json={"enabled": True, "fallback_file_id": fid}).status_code == 200
    detail = client.get(f"/api/stations/{sid}").json()
    assert detail["playout"]["mode"] == "fallback" and detail["on_air"]
    t = now()
    body = {"title": "Scheduled show", "format": "prerecorded", "file_id": fid, "start": (t-timedelta(minutes=1)).isoformat(), "end": (t+timedelta(minutes=20)).isoformat()}
    p = client.post(root + "/programmes", json=body, headers=h).json()
    assert client.get(f"/api/stations/{sid}").json()["playout"]["mode"] == "scheduled"
    session = client.post("/api/broadcast/sessions", headers=h, json={"title": "Presenter"}).json()
    assert client.post(f"/api/broadcast/sessions/{session['id']}/start", headers=h).status_code == 200
    assert client.get(f"/api/stations/{sid}").json()["playout"]["mode"] == "live"
    assert client.post(f"/api/broadcast/sessions/{session['id']}/stop", headers=h).status_code == 200
    assert client.get(f"/api/stations/{sid}").json()["playout"]["mode"] == "scheduled"
    assert client.delete(root + f"/programmes/{p['id']}", headers=h).status_code == 200
    assert client.get(f"/api/stations/{sid}").json()["playout"]["mode"] == "fallback"
    assert client.put(root + "/automation", headers=h, json={"enabled": False}).status_code == 200
    assert not client.get(f"/api/stations/{sid}").json()["on_air"]
