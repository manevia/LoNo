import uuid


def make_user(client, name="Creator"):
    email = f"c_{uuid.uuid4().hex[:8]}@example.com"
    d = client.post("/api/auth/register", json={"email": email, "password": "Passw0rd!", "name": name, "accept_terms": True}).json()
    return {"id": d["user"]["id"], "h": {"Authorization": f"Bearer {d['token']}"}}


COURSE = {
    "title": "Podcasting on a Budget",
    "description": "Record, edit and publish a podcast with gear you already own.",
    "level": "Beginner",
    "lessons": [
        {"title": "Your phone is a microphone", "body": "Record in a small room with soft furnishings."},
        {"title": "Editing basics", "body": "Cut long pauses, then normalise loudness."},
    ],
    "questions": [
        {"prompt": "Best room to record in?", "options": ["Bathroom", "Small furnished room"], "answer_index": 1},
        {"prompt": "First edit to make?", "options": ["Add music", "Cut long pauses"], "answer_index": 1},
        {"prompt": "What evens out volume?", "options": ["Normalising", "Reverb", "Panning"], "answer_index": 0},
    ],
}


def bal(client, u):
    return client.get("/api/wallet", headers=u["h"]).json()["wallet"]["lono_balance"]


def catalogue_ids(client):
    return {c["id"] for c in client.get("/api/learn/courses").json()}


def pass_course(client, u, course_id):
    c = client.get(f"/api/learn/courses/{course_id}", headers=u["h"]).json()
    client.post(f"/api/learn/courses/{course_id}/enroll", headers=u["h"])
    for l in c["lessons"]:
        client.post(f"/api/learn/courses/{course_id}/lessons/{l['id']}/complete", headers=u["h"])
    answers = {q["id"]: a["answer_index"] for q, a in zip(c["quiz"]["questions"], COURSE["questions"])}
    return client.post(f"/api/learn/courses/{course_id}/quiz", json={"answers": answers}, headers=u["h"]).json()


def test_draft_is_private_until_published(client):
    me = make_user(client)
    draft = client.post("/api/creator/courses", json={"title": "Untitled course"}, headers=me["h"]).json()
    assert draft["status"] == "draft" and draft["problems"]
    assert draft["id"] not in catalogue_ids(client)
    assert client.get(f"/api/learn/courses/{draft['id']}").status_code == 404
    r = client.post(f"/api/creator/courses/{draft['id']}/publish", headers=me["h"])
    assert r.status_code == 422 and "at least one lesson" in r.json()["detail"]


def test_full_lifecycle_and_payouts(client):
    me, learner = make_user(client, "Teacher"), make_user(client, "Learner")
    c = client.post("/api/creator/courses", json=COURSE, headers=me["h"]).json()
    assert c["problems"] == [] and c["reward_lono"] == 10
    pub = client.post(f"/api/creator/courses/{c['id']}/publish", headers=me["h"]).json()
    assert pub["status"] == "published" and c["id"] in catalogue_ids(client)
    item = client.get(f"/api/content/{pub['content_id']}").json()
    assert item["kind"] == "course" and item["course_id"] == c["id"]
    # learner never sees the answers
    public = client.get(f"/api/learn/courses/{c['id']}").json()
    assert all("answer_index" not in q for q in public["quiz"]["questions"])

    before_me, before_l = bal(client, me), bal(client, learner)
    res = pass_course(client, learner, c["id"])
    assert res["passed"] and res["reward"] == 10
    assert bal(client, learner) == before_l + 10
    assert bal(client, me) == before_me + 2  # creator payout

    # creator passing their own course earns nothing for anyone
    before_me = bal(client, me)
    own = pass_course(client, me, c["id"])
    assert own["passed"] and own["reward"] == 0 and bal(client, me) == before_me

    mine = client.get("/api/creator/courses", headers=me["h"]).json()
    row = next(x for x in mine if x["id"] == c["id"])
    assert row["certificates_issued"] == 2 and row["enrolled"] == 2

    # certificates protect the course from deletion
    assert client.delete(f"/api/creator/courses/{c['id']}", headers=me["h"]).status_code == 400
    client.post(f"/api/creator/courses/{c['id']}/unpublish", headers=me["h"])
    assert c["id"] not in catalogue_ids(client)
    assert client.get(f"/api/content/{pub['content_id']}").status_code == 404


def test_edits_keep_progress_and_validate(client):
    me, learner = make_user(client), make_user(client)
    c = client.post("/api/creator/courses", json=COURSE, headers=me["h"]).json()
    client.post(f"/api/creator/courses/{c['id']}/publish", headers=me["h"])
    l1, l2 = c["lessons"]
    client.post(f"/api/learn/courses/{c['id']}/enroll", headers=learner["h"])
    client.post(f"/api/learn/courses/{c['id']}/lessons/{l1['id']}/complete", headers=learner["h"])

    body = {**COURSE, "lessons": [
        {"id": l1["id"], "title": "Your phone is a microphone (updated)", "body": "New text"},
        {"title": "Publishing your feed", "body": "Use a host that makes an RSS feed."}],
        "questions": [{**q, "id": qq["id"]} for q, qq in zip(COURSE["questions"], c["quiz"]["questions"])]}
    upd = client.put(f"/api/creator/courses/{c['id']}", json=body, headers=me["h"]).json()
    assert upd["lessons"][0]["id"] == l1["id"]
    p = client.get(f"/api/learn/courses/{c['id']}", headers=learner["h"]).json()["progress"]
    assert p["lessons_done"] == 1 and p["lessons_total"] == 2  # removed lesson no longer counts

    # a published course can't be emptied
    r = client.put(f"/api/creator/courses/{c['id']}", json={**body, "questions": []}, headers=me["h"])
    assert r.status_code == 422
    # bad answer index and duplicate options are rejected
    bad = {**COURSE, "questions": [{"prompt": "x?", "options": ["a", "b"], "answer_index": 5}]}
    assert client.post("/api/creator/courses", json=bad, headers=me["h"]).status_code == 422
    dup = {**COURSE, "questions": [{"prompt": "x?", "options": ["Yes", "yes"], "answer_index": 0}]}
    assert client.post("/api/creator/courses", json=dup, headers=me["h"]).status_code == 422


def test_only_owner_can_edit(client):
    me, other = make_user(client), make_user(client)
    c = client.post("/api/creator/courses", json=COURSE, headers=me["h"]).json()
    assert client.get(f"/api/creator/courses/{c['id']}", headers=other["h"]).status_code == 404
    assert client.put(f"/api/creator/courses/{c['id']}", json=COURSE, headers=other["h"]).status_code == 404
    assert client.post(f"/api/creator/courses/{c['id']}/publish", headers=other["h"]).status_code == 404
    assert client.delete(f"/api/creator/courses/{c['id']}", headers=me["h"]).status_code == 200


def test_seeded_courses_have_no_owner_payout(client, user):
    seeded = [c for c in client.get("/api/learn/courses").json() if c["title"] == "Broadcasting 101: Radio to Streaming"]
    assert seeded and seeded[0].get("owner_id") is None


def test_ai_question_suggestions(client, monkeypatch):
    import app.routers.creator_courses as cc
    me = make_user(client)
    short = {**COURSE, "lessons": [{"title": "Hi", "body": "Short."}]}
    c = client.post("/api/creator/courses", json=short, headers=me["h"]).json()
    assert client.post(f"/api/creator/courses/{c['id']}/suggest-questions", json={}, headers=me["h"]).status_code == 400

    long_body = {**COURSE, "lessons": [{"title": "Rooms", "body": "Soft furnishings absorb echo. " * 10}]}
    client.put(f"/api/creator/courses/{c['id']}", json=long_body, headers=me["h"])
    # with no ANTHROPIC_API_KEY the feature reports itself as off
    assert client.post(f"/api/creator/courses/{c['id']}/suggest-questions", json={}, headers=me["h"]).status_code == 503

    async def fake(system, messages, max_tokens=800):
        return 'Here you go:\n[{"prompt": "What absorbs echo?", "options": ["Glass", "Soft furnishings", "Tile"], '\
               '"answer_index": 1, "explanation": "Soft surfaces absorb sound."}, '\
               '{"prompt": "Broken", "options": ["A", "B"], "answer_index": 7}]'
    monkeypatch.setattr(cc.ai, "complete", fake)
    r = client.post(f"/api/creator/courses/{c['id']}/suggest-questions", json={"count": 3}, headers=me["h"])
    assert r.status_code == 200
    qs = r.json()["questions"]
    assert len(qs) == 1 and qs[0]["answer_index"] == 1  # invalid suggestion dropped
    # suggestions are not saved automatically
    assert len(client.get(f"/api/creator/courses/{c['id']}", headers=me["h"]).json()["quiz"]["questions"]) == 3

    async def junk(*a, **k):
        return "sorry, no"
    monkeypatch.setattr(cc.ai, "complete", junk)
    assert client.post(f"/api/creator/courses/{c['id']}/suggest-questions", json={}, headers=me["h"]).status_code == 502
