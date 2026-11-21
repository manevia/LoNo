import asyncio


def test_documentary_release_and_trailer_visibility(client, user, admin):
    from app.db import db
    from app.routers.editorial import process_release

    h = user["h"]
    cid = client.get("/api/creator/profile", headers=h).json()["id"]
    root = f"/api/creator/editorial/{cid}"
    body = {"title": "Documentary test", "category": "Education", "kind": "movie",
            "film": {"format": "documentary", "genres": ["Culture"], "collection": "Test films",
                     "runtime_minutes": 20, "credits": [{"name": "Test director", "role": "Director"}]}}
    d = client.post(root, headers=h, json=body).json()
    ep = root + "/" + d["id"]
    media = client.post(ep+"/assets", headers=h, files={"file": ("film.mp4", b"sample", "video/mp4")}).json()
    trailer = client.post(ep+"/assets", headers=h, files={"file": ("trailer.mp4", b"sample", "video/mp4")}).json()
    preview = client.get(ep+f"/assets/{trailer['id']}/preview", headers=h).json()["url"]
    url = preview.split("?")[0]
    body.update(media_id=media["id"], revision=0)
    body["film"]["trailer_id"] = trailer["id"]
    assert client.put(ep, headers=h, json=body).status_code == 200
    assert client.get(url).status_code == 403
    def catalogue():
        return client.get("/api/films", params={"format": "documentary", "genre": "Culture", "collection": "Test films"}).json()["items"]
    assert not any(x["id"] == d["id"] for x in catalogue())
    for rev, action in [(1, "submit"), (2, "approve"), (3, "schedule")]:
        assert client.post(ep+"/decision", headers=h, json={"action": action, "revision": rev, "publish_at": "2099-01-01T00:00:00Z"}).status_code == 200
    async def release():
        await process_release(await db.editorial_drafts.find_one({"id": d["id"]}, {"_id": 0}))
    asyncio.run(release())
    movie = next(x for x in catalogue() if x["id"] == d["id"])
    assert movie["film"]["format"] == "documentary"
    assert "trailer_id" not in movie["film"]
    assert movie["duration_sec"] == 1200
    assert client.get(url).status_code == 200
    row = next(x for x in client.get(root, headers=h).json() if x["id"] == d["id"])
    assert client.post(f"/api/admin/editorial/{d['id']}/suspend", headers=admin["h"], json={"action": "suspend", "revision": row["revision"], "reason": "Test moderation"}).status_code == 200
    assert not any(x["id"] == d["id"] for x in catalogue())
    assert client.get(url).status_code == 403
