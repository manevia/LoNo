import csv
import io

from test_course_builder import COURSE, make_user, pass_course


def test_signup_requires_consent_and_records_it(client):
    body = {"email": "noconsent@example.com", "password": "Passw0rd!", "name": "N"}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 400 and "Terms" in r.json()["detail"]
    r = client.post("/api/auth/register", json={**body, "accept_terms": True})
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert me["consents"][0]["version"] == me["terms_version"] and me["needs_terms"] is False
    assert me["is_admin"] is False


def test_admin_only(client, user, admin):
    for path in ("/api/admin/overview", "/api/admin/reports", "/api/admin/users", "/api/admin/audit"):
        assert client.get(path, headers=user["h"]).status_code == 403
        assert client.get(path).status_code == 401
        assert client.get(path, headers=admin["h"]).status_code == 200
    assert client.get("/api/auth/me", headers=admin["h"]).json()["is_admin"] is True
    ov = client.get("/api/admin/overview", headers=admin["h"]).json()
    assert ov["users"] >= 2 and "open_reports" in ov


def _reviewed_course(client):
    owner, a, b = make_user(client, "Owner"), make_user(client, "Writer"), make_user(client, "Reader")
    c = client.post("/api/creator/courses", json=COURSE, headers=owner["h"]).json()
    client.post(f"/api/creator/courses/{c['id']}/publish", headers=owner["h"])
    for u in (a, b):
        pass_course(client, u, c["id"])
    client.put(f"/api/learn/courses/{c['id']}/review", json={"rating": 1, "text": "spam spam buy now"}, headers=a["h"])
    client.put(f"/api/learn/courses/{c['id']}/review", json={"rating": 5, "text": "Great"}, headers=b["h"])
    rid = next(r["id"] for r in client.get(f"/api/learn/courses/{c['id']}/reviews").json()["items"] if r["rating"] == 1)
    return c, a, b, rid


def test_report_and_hide_review(client, admin):
    c, a, b, rid = _reviewed_course(client)
    assert client.post(f"/api/learn/reviews/{rid}/report", json={"reason": "Spam"}, headers=a["h"]).status_code == 400  # own
    assert client.post(f"/api/learn/reviews/{rid}/report", json={"reason": "Spam link"}, headers=b["h"]).json()["ok"]
    assert client.post(f"/api/learn/reviews/{rid}/report", json={"reason": "Spam link"}, headers=b["h"]).json()["already_reported"]
    queue = client.get("/api/admin/reports", headers=admin["h"]).json()
    rep = next(r for r in queue if r["target_id"] == rid)
    assert rep["review"]["text"] == "spam spam buy now" and rep["reporter_name"] == "Reader"

    assert client.post(f"/api/admin/reports/{rep['id']}/resolve", json={"action": "hide"}, headers=admin["h"]).json()["ok"]
    data = client.get(f"/api/learn/courses/{c['id']}/reviews").json()
    assert [r["rating"] for r in data["items"]] == [5] and data["summary"]["average"] == 5.0
    assert client.post(f"/api/admin/reports/{rep['id']}/resolve", json={"action": "hide"}, headers=admin["h"]).status_code == 409
    assert client.post(f"/api/learn/reviews/{rid}/report", json={"reason": "again"}, headers=b["h"]).status_code == 404

    client.post(f"/api/admin/reviews/{rid}/restore", headers=admin["h"])
    assert client.get(f"/api/learn/courses/{c['id']}/reviews").json()["summary"]["average"] == 3.0


def test_suspend_and_reinstate(client, admin):
    u = make_user(client, "Troll")
    email = client.get("/api/auth/me", headers=u["h"]).json()["email"]
    assert client.post(f"/api/admin/users/{u['id']}/suspend", json={"reason": "Abuse in reviews"}, headers=admin["h"]).json()["suspended"]
    assert client.get("/api/wallet", headers=u["h"]).status_code == 403
    assert client.post("/api/auth/login", json={"email": email, "password": "Passw0rd!"}).status_code == 403
    found = client.get("/api/admin/users", params={"q": "Troll"}, headers=admin["h"]).json()
    assert found and found[0]["suspended"] is True
    client.post(f"/api/admin/users/{u['id']}/reinstate", headers=admin["h"])
    assert client.get("/api/wallet", headers=u["h"]).status_code == 200
    assert client.post(f"/api/admin/users/{admin['id']}/suspend", json={"reason": "test"}, headers=admin["h"]).status_code == 400


def test_admin_unpublish_course(client, admin):
    owner = make_user(client)
    c = client.post("/api/creator/courses", json=COURSE, headers=owner["h"]).json()
    client.post(f"/api/creator/courses/{c['id']}/publish", headers=owner["h"])
    assert any(x["id"] == c["id"] and x["status"] == "published" for x in client.get("/api/admin/courses", headers=admin["h"]).json())
    client.post(f"/api/admin/courses/{c['id']}/unpublish", json={"reason": "Copied material"}, headers=admin["h"])
    assert c["id"] not in {x["id"] for x in client.get("/api/learn/courses").json()}
    assert client.get(f"/api/creator/courses/{c['id']}", headers=owner["h"]).json()["moderation_note"] == "Copied material"


def test_audit_trail_and_csv(client, admin):
    u = make_user(client, "=HYPERLINK(\"http://x\")")
    email = client.get("/api/auth/me", headers=u["h"]).json()["email"]
    client.get("/api/me/export", headers=u["h"])
    client.request("DELETE", "/api/me", json={"confirm_email": email, "password": "Passw0rd!"}, headers=u["h"])
    log = client.get("/api/admin/audit", headers=admin["h"]).json()
    mine = [e for e in log["items"] if e["target"] == u["id"]]
    assert {e["action"] for e in mine} >= {"account_created", "data_export", "account_deleted"}
    deleted = next(e for e in mine if e["action"] == "account_deleted")
    assert "subject_email_hash" in deleted and email not in str(log)       # no plain email kept
    assert all(e["actor_name"] is None for e in mine)                        # name scrubbed after erasure
    only = client.get("/api/admin/audit", params={"action": "account_deleted"}, headers=admin["h"]).json()
    assert all(e["action"] == "account_deleted" for e in only["items"])

    r = client.get("/api/admin/audit.csv", headers=admin["h"])
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0][:2] == ["at", "action"]
    assert not any(cell.startswith("=") for row in rows for cell in row)    # formula injection neutralised


def test_csv_neutralises_formula_names(client, admin):
    u = make_user(client, "=SUM(1,2)")
    client.get("/api/me/export", headers=u["h"])
    rows = list(csv.reader(io.StringIO(client.get("/api/admin/audit.csv", headers=admin["h"]).content.decode("utf-8-sig"))))
    names = [r[3] for r in rows[1:] if r[2] == u["id"]]
    assert names and all(n == "'=SUM(1,2)" for n in names)


def test_republish_clears_moderation_note(client, admin):
    owner = make_user(client)
    c = client.post("/api/creator/courses", json=COURSE, headers=owner["h"]).json()
    client.post(f"/api/creator/courses/{c['id']}/publish", headers=owner["h"])
    client.post(f"/api/admin/courses/{c['id']}/unpublish", json={"reason": "Fix the quiz"}, headers=admin["h"])
    client.post(f"/api/creator/courses/{c['id']}/publish", headers=owner["h"])
    assert client.get(f"/api/creator/courses/{c['id']}", headers=owner["h"]).json()["moderation_note"] is None
