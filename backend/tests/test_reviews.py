from test_course_builder import COURSE, make_user, pass_course


def setup_course(client):
    owner = make_user(client, "Owner")
    c = client.post("/api/creator/courses", json=COURSE, headers=owner["h"]).json()
    client.post(f"/api/creator/courses/{c['id']}/publish", headers=owner["h"])
    return owner, c


def test_only_passed_learners_review(client):
    owner, c = setup_course(client)
    stranger, learner = make_user(client), make_user(client, "Ama")
    body = {"rating": 5, "text": "Clear and practical."}
    assert client.put(f"/api/learn/courses/{c['id']}/review", json=body, headers=stranger["h"]).status_code == 403
    assert client.put(f"/api/learn/courses/{c['id']}/review", json=body, headers=owner["h"]).status_code == 400
    assert client.put(f"/api/learn/courses/{c['id']}/review", json=body).status_code == 401
    assert client.get(f"/api/learn/courses/{c['id']}/reviews", headers=stranger["h"]).json()["can_review"] is False

    pass_course(client, learner, c["id"])
    assert client.get(f"/api/learn/courses/{c['id']}/reviews", headers=learner["h"]).json()["can_review"] is True
    r = client.put(f"/api/learn/courses/{c['id']}/review", json=body, headers=learner["h"]).json()
    assert r["summary"] == {"average": 5.0, "count": 1, "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 1}}
    assert r["review"]["user_name"] == "Ama" and "user_id" not in r["review"]


def test_average_edit_and_delete(client):
    owner, c = setup_course(client)
    a, b = make_user(client), make_user(client)
    for u in (a, b):
        pass_course(client, u, c["id"])
    client.put(f"/api/learn/courses/{c['id']}/review", json={"rating": 5}, headers=a["h"])
    client.put(f"/api/learn/courses/{c['id']}/review", json={"rating": 2}, headers=b["h"])
    s = client.get(f"/api/learn/courses/{c['id']}/reviews").json()["summary"]
    assert s["average"] == 3.5 and s["count"] == 2

    # editing replaces the learner's review instead of adding a second one
    client.put(f"/api/learn/courses/{c['id']}/review", json={"rating": 4, "text": "Better on a second look"}, headers=b["h"])
    data = client.get(f"/api/learn/courses/{c['id']}/reviews", headers=b["h"]).json()
    assert data["summary"]["average"] == 4.5 and data["summary"]["count"] == 2
    assert data["mine"]["rating"] == 4 and len(data["items"]) == 2

    # the rating shows on the catalogue, the course card and the creator's studio
    listed = next(x for x in client.get("/api/learn/courses").json() if x["id"] == c["id"])
    assert listed["rating_avg"] == 4.5 and listed["rating_count"] == 2
    content_id = client.get(f"/api/creator/courses/{c['id']}", headers=owner["h"]).json()["content_id"]
    content = client.get(f"/api/content/{content_id}").json()
    assert content["rating"] == 4.5
    studio = next(x for x in client.get("/api/creator/courses", headers=owner["h"]).json() if x["id"] == c["id"])
    assert studio["rating_avg"] == 4.5

    assert client.delete(f"/api/learn/courses/{c['id']}/review", headers=a["h"]).json()["summary"]["average"] == 4.0
    assert client.delete(f"/api/learn/courses/{c['id']}/review", headers=a["h"]).status_code == 404


def test_rating_validation(client):
    owner, c = setup_course(client)
    u = make_user(client)
    pass_course(client, u, c["id"])
    for bad in ({"rating": 0}, {"rating": 6}, {"rating": 3, "text": "x" * 1001}):
        assert client.put(f"/api/learn/courses/{c['id']}/review", json=bad, headers=u["h"]).status_code == 422
