import json
import uuid

from test_course_builder import COURSE, make_user, pass_course


def test_profile_update_and_review_name(client, user):
    r = client.patch("/api/auth/me", json={"name": "  New Name "}, headers=user["h"])
    assert r.status_code == 200 and r.json()["name"] == "New Name" and "password_hash" not in r.json()
    assert client.patch("/api/auth/me", json={"name": ""}, headers=user["h"]).status_code == 422


def test_change_password(client, user):
    bad = {"current_password": "wrong", "new_password": "N3wPassword!"}
    assert client.post("/api/auth/password", json=bad, headers=user["h"]).status_code == 400
    ok = {"current_password": "Passw0rd!", "new_password": "N3wPassword!"}
    assert client.post("/api/auth/password", json=ok, headers=user["h"]).status_code == 200
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "Passw0rd!"}).status_code == 400
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "N3wPassword!"}).status_code == 200
    short = {"current_password": "N3wPassword!", "new_password": "short"}
    assert client.post("/api/auth/password", json=short, headers=user["h"]).status_code == 422


def test_export_contains_my_data_only(client, user):
    other = make_user(client)
    client.post("/api/wallet/stake", json={"amount": 10, "lock_days": 30}, headers=user["h"])
    r = client.get("/api/me/export", headers=user["h"])
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    d = json.loads(r.content)
    assert d["account"]["email"] == user["email"] and "password_hash" not in d["account"]
    assert len(d["stakes"]) == 1 and {t["kind"] for t in d["transactions"]} >= {"signup_bonus", "stake"}
    assert all(t["user_id"] == user["id"] for t in d["transactions"])
    assert other["id"] not in r.text


def test_delete_account_erases_and_keeps_tallies(client):
    me = make_user(client, "Leaving")
    email = client.get("/api/auth/me", headers=me["h"]).json()["email"]
    # activity to clean up
    creator = make_user(client, "Creator")
    c = client.post("/api/creator/courses", json=COURSE, headers=creator["h"]).json()
    client.post(f"/api/creator/courses/{c['id']}/publish", headers=creator["h"])
    pass_course(client, me, c["id"])
    client.put(f"/api/learn/courses/{c['id']}/review", json={"rating": 2, "text": "meh"}, headers=me["h"])
    prop = next(p for p in client.get("/api/governance/proposals").json() if p["status"] == "active")
    client.post("/api/governance/vote", json={"proposal_id": prop["id"], "choice": "against"}, headers=me["h"])
    votes_before = next(p for p in client.get("/api/governance/proposals").json() if p["id"] == prop["id"])["votes"]
    ch = client.get("/api/channels").json()[0]
    subs_before = client.post(f"/api/channels/{ch['id']}/subscribe", headers=me["h"]).json()["subscribers"]
    up = client.post("/api/storage/upload", files={"file": ("a.mp4", b"x" * 100, "video/mp4")}, headers=me["h"]).json()

    assert client.request("DELETE", "/api/me", json={"confirm_email": "wrong@example.com", "password": "Passw0rd!"},
                          headers=me["h"]).status_code == 400
    assert client.request("DELETE", "/api/me", json={"confirm_email": email, "password": "nope"},
                          headers=me["h"]).status_code == 400
    r = client.request("DELETE", "/api/me", json={"confirm_email": email.upper(), "password": "Passw0rd!"}, headers=me["h"])
    assert r.status_code == 200

    assert client.get("/api/auth/me", headers=me["h"]).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": "Passw0rd!"}).status_code == 400
    reviews = client.get(f"/api/learn/courses/{c['id']}/reviews").json()
    assert reviews["summary"]["count"] == 0 and reviews["items"] == []
    after = next(p for p in client.get("/api/governance/proposals").json() if p["id"] == prop["id"])["votes"]
    assert after == votes_before  # vote tally kept, link to the person removed
    assert client.get(f"/api/channels/{ch['id']}").json()["subscribers"] == subs_before - 1
    assert client.get(up["url"]).status_code == 404
    # the email can be used again
    again = client.post("/api/auth/register", json={"email": email, "password": "Passw0rd!", "name": "Back"})
    assert again.status_code == 200


def test_two_deleted_voters_on_same_proposal(client):
    prop = next(p for p in client.get("/api/governance/proposals").json() if p["status"] == "active")
    for _ in range(2):
        u = make_user(client)
        email = client.get("/api/auth/me", headers=u["h"]).json()["email"]
        client.post("/api/governance/vote", json={"proposal_id": prop["id"], "choice": "for"}, headers=u["h"])
        r = client.request("DELETE", "/api/me", json={"confirm_email": email, "password": "Passw0rd!"}, headers=u["h"])
        assert r.status_code == 200, r.text
