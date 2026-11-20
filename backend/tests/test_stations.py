"""Permanent station and schedule integration tests; no real encoder required."""
from datetime import timedelta

from app.util import now
from test_broadcast import media_on


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
