def correct_answers(course_id):
    import asyncio
    from app.db import db
    c = asyncio.run(db.courses.find_one({"id": course_id}))
    return {q["id"]: q["answer_index"] for q in c["quiz"]["questions"]}


def test_learn_flow(client, user):
    courses = client.get("/api/learn/courses").json()
    assert len(courses) == 3
    c = client.get(f"/api/learn/courses/{courses[0]['id']}").json()
    assert all("answer_index" not in q for q in c["quiz"]["questions"])
    cid = c["id"]
    h = user["h"]
    assert client.post(f"/api/learn/courses/{cid}/quiz", json={"answers": {}}, headers=h).status_code == 400
    client.post(f"/api/learn/courses/{cid}/enroll", headers=h)
    assert client.post(f"/api/learn/courses/{cid}/quiz", json={"answers": {}}, headers=h).status_code == 400
    for l in c["lessons"]:
        p = client.post(f"/api/learn/courses/{cid}/lessons/{l['id']}/complete", headers=h).json()
    assert p["percent"] == 100

    wrong = client.post(f"/api/learn/courses/{cid}/quiz", json={"answers": {}}, headers=h).json()
    assert wrong["passed"] is False and wrong["reward"] == 0
    assert all("answer_index" not in r for r in wrong["results"])  # failing doesn't leak answers
    answers = correct_answers(cid)
    ok = client.post(f"/api/learn/courses/{cid}/quiz", json={"answers": answers}, headers=h).json()
    assert ok["passed"] and ok["reward"] == c["reward_lono"] and ok["certificate"]
    assert all("explanation" in r for r in ok["results"])
    again = client.post(f"/api/learn/courses/{cid}/quiz", json={"answers": answers}, headers=h).json()
    assert again["reward"] == 0 and again["certificate_id"] == ok["certificate"]["id"]

    cert = client.get(f"/api/learn/certificates/{ok['certificate']['id']}").json()
    assert cert["valid"] is True and cert["course_title"] == c["title"]
    me = client.get("/api/learn/me", headers=h).json()
    assert len(me["certificates"]) == 1
    assert client.get("/api/wallet", headers=h).json()["wallet"]["lono_balance"] == 100 + c["reward_lono"]


def test_tampered_certificate_detected(client, user):
    import asyncio
    from app.db import db
    c = client.get("/api/learn/courses").json()[1]
    h = user["h"]
    client.post(f"/api/learn/courses/{c['id']}/enroll", headers=h)
    for l in c["lessons"]:
        client.post(f"/api/learn/courses/{c['id']}/lessons/{l['id']}/complete", headers=h)
    ans = correct_answers(c["id"])
    cert_id = client.post(f"/api/learn/courses/{c['id']}/quiz", json={"answers": ans}, headers=h).json()["certificate"]["id"]
    asyncio.run(db.certificates.update_one({"id": cert_id}, {"$set": {"score": 0.1}}))
    assert client.get(f"/api/learn/certificates/{cert_id}").json()["valid"] is False


def test_upload_and_range_playback(client, user):
    data = bytes(range(256)) * 400  # 102,400 bytes
    r = client.post("/api/storage/upload", files={"file": ("clip.mp4", data, "video/mp4")}, headers=user["h"])
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    full = client.get(url)
    assert full.status_code == 200 and full.content == data
    part = client.get(url, headers={"Range": "bytes=100-199"})
    assert part.status_code == 206 and part.content == data[100:200]
    assert part.headers["content-range"] == f"bytes 100-199/{len(data)}"
    assert client.post("/api/storage/upload", files={"file": ("x.exe", b"MZ", "application/x-msdownload")},
                       headers=user["h"]).status_code == 400
    assert client.get("/api/files/../../etc/passwd").status_code == 404


def test_creator_flow(client, user):
    dash = client.get("/api/creator/dashboard", headers=user["h"]).json()
    assert dash["stats"]["videos_count"] == 0 and len(dash["chart"]) == 14
    item = client.post("/api/creator/upload", headers=user["h"], json={
        "title": "My first show", "description": "Pilot", "kind": "short", "category": "Comedy",
        "thumbnail_url": "https://example.com/t.jpg", "stream_url": "https://example.com/v.mp4"}).json()
    client.post("/api/watch/start", json={"content_id": item["id"]})
    dash = client.get("/api/creator/dashboard", headers=user["h"]).json()
    assert dash["stats"]["videos_count"] == 1 and dash["chart"][-1]["views"] == 1
    assert client.delete(f"/api/creator/content/{item['id']}", headers=user["h"]).status_code == 200
