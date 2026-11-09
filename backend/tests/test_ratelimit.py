import uuid

import app.routers.auth as auth


def test_login_lockout_after_repeated_failures(client, user):
    auth.login_failures.clear()
    bad = {"email": user["email"], "password": "wrong-password"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=bad).status_code == 400
    r = client.post("/api/auth/login", json=bad)
    assert r.status_code == 429 and "Too many failed sign-in attempts" in r.json()["detail"]
    assert int(r.headers["retry-after"]) > 0
    # even the right password waits until the window passes
    good = {"email": user["email"], "password": "Passw0rd!"}
    assert client.post("/api/auth/login", json=good).status_code == 429
    auth.login_failures.clear()
    assert client.post("/api/auth/login", json=good).status_code == 200


def test_success_resets_failure_count(client, user):
    auth.login_failures.clear()
    bad = {"email": user["email"], "password": "nope-nope"}
    good = {"email": user["email"], "password": "Passw0rd!"}
    for _ in range(4):
        client.post("/api/auth/login", json=bad)
    assert client.post("/api/auth/login", json=good).status_code == 200
    for _ in range(4):
        assert client.post("/api/auth/login", json=bad).status_code == 400  # counter started over


def test_lockout_is_per_account(client, user):
    auth.login_failures.clear()
    for _ in range(6):
        client.post("/api/auth/login", json={"email": user["email"], "password": "bad-guess"})
    other = client.post("/api/auth/login", json={"email": "someone-else@example.com", "password": "x"})
    assert other.status_code == 400
    auth.login_failures.clear()


def test_signup_limit_per_network(client, monkeypatch):
    monkeypatch.setattr(auth.signups, "limit", 2)
    auth.signups.clear()
    mk = lambda: client.post("/api/auth/register", json={
        "email": f"s_{uuid.uuid4().hex[:8]}@example.com", "password": "Passw0rd!", "name": "S"})
    assert mk().status_code == 200 and mk().status_code == 200
    r = mk()
    assert r.status_code == 429 and "Too many new accounts" in r.json()["detail"]
    auth.signups.clear()
