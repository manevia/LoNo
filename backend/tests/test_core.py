def test_health_and_config(client):
    assert client.get("/api/health").json()["status"] == "healthy"
    cfg = client.get("/api/config").json()
    assert cfg["ai"] is False and cfg["payments"] is False and cfg["storage"] == "local"


def test_catalogue_seeded(client):
    items = client.get("/api/content", params={"limit": 200}).json()
    assert len(items) >= 29
    kinds = {i["kind"] for i in items}
    assert {"movie", "series", "podcast", "music", "live_tv", "live_radio", "course"} <= kinds
    rails = client.get("/api/content/rails").json()
    assert any(r["key"] == "learn" for r in rails)
    assert all(r["items"] for r in rails)


def test_search_escapes_regex(client):
    assert client.get("/api/search", params={"q": "("}).status_code == 200
    assert any("Solar" in i["title"] for i in client.get("/api/search", params={"q": "solar"}).json())


def test_register_login_me(client, user):
    r = client.post("/api/auth/login", json={"email": user["email"], "password": "Passw0rd!"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=user["h"]).json()
    assert me["wallet"]["lono_balance"] == 100 and "password_hash" not in me
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "nope"}).status_code == 400
    dup = client.post("/api/auth/register", json={"email": user["email"], "password": "Passw0rd!", "name": "X", "accept_terms": True})
    assert dup.status_code == 400


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "s@example.com", "password": "short", "name": "S"})
    assert r.status_code == 422


def test_auth_required(client):
    assert client.get("/api/wallet").status_code == 401
    assert client.get("/api/wallet", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_optional_features_report_503(client, user):
    cid = client.get("/api/content").json()[0]["id"]
    assert client.post("/api/ai/chat", json={"message": "hi"}).status_code == 503
    assert client.post("/api/ai/summarize", json={"content_id": cid}).status_code == 503
    assert client.post("/api/payments/checkout", json={"plan": "premium"}, headers=user["h"]).status_code == 503
    assert client.post("/api/auth/google", json={"credential": "x"}).status_code == 503


def test_like_list_subscribe(client, user):
    item = client.get("/api/content", params={"kind": "movie"}).json()[0]
    r = client.post(f"/api/content/{item['id']}/like", headers=user["h"]).json()
    assert r["liked"] is True and r["likes"] == item["likes"] + 1
    assert client.post(f"/api/content/{item['id']}/like", headers=user["h"]).json()["liked"] is False
    assert client.post(f"/api/content/{item['id']}/list", headers=user["h"]).json()["in_list"] is True
    assert [i["id"] for i in client.get("/api/me/list", headers=user["h"]).json()] == [item["id"]]
    detail = client.get(f"/api/content/{item['id']}", headers=user["h"]).json()
    assert detail["viewer"]["in_list"] is True
    s = client.post(f"/api/channels/{item['channel_id']}/subscribe", headers=user["h"]).json()
    assert s["subscribed"] is True
    rails = client.get("/api/content/rails", headers=user["h"]).json()
    assert rails[0]["key"] == "mylist"


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert "strict-origin" in r.headers["referrer-policy"]


def test_assetlinks(client, monkeypatch):
    from app import config
    assert client.get("/.well-known/assetlinks.json").json() == []
    monkeypatch.setattr(config, "ANDROID_APP_PACKAGE", "lr.edu.ciu.lono")
    monkeypatch.setattr(config, "ANDROID_CERT_SHA256", ["AA:BB"])
    d = client.get("/.well-known/assetlinks.json").json()
    assert d[0]["target"]["package_name"] == "lr.edu.ciu.lono" and d[0]["target"]["sha256_cert_fingerprints"] == ["AA:BB"]


def test_permissions_policy_allows_studio_devices(client):
    pp = client.get("/api/health").headers["permissions-policy"]
    assert "camera=(self)" in pp and "microphone=(self)" in pp and "geolocation=()" in pp
