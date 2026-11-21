from test_course_builder import make_user


def test_private_editorial_assets_and_roles(client,user,admin):
    owner=user["h"]
    other=make_user(client); stranger=other["h"]
    cid=client.get("/api/creator/profile",headers=owner).json()["id"]
    root=f"/api/creator/editorial/{cid}"
    assert client.get(root,headers=stranger).status_code==404
    d=client.post(root,headers=owner,json={"title":"Private editorial title","category":"Education","kind":"short"}).json()
    ep=root+"/"+d["id"]
    assert client.get(f"/api/content/{d['id']}").status_code==404
    asset=client.post(ep+"/assets",headers=owner,files={"file":("video.mp4",b"sample", "video/mp4")}).json()
    assert client.get(ep+"/assets",headers=stranger).status_code==404
    preview=client.get(ep+f"/assets/{asset['id']}/preview",headers=owner).json()["url"]
    assert client.get(preview.split("?")[0]).status_code==403
    assert client.get(preview).status_code==200
    body={"title":"Private editorial title","category":"Education","kind":"short","media_id":asset["id"],"revision":0}
    assert client.put(ep,headers=owner,json=body).status_code==200
    assert client.put(ep,headers=owner,json=body).status_code==409
    row=client.get(root,headers=owner).json()[0]
    assert len(row["versions"])==2
    assert client.post(ep+"/decision",headers=owner,json={"action":"schedule","revision":1}).status_code==409
    assert client.post(ep+"/decision",headers=owner,json={"action":"submit","revision":1}).status_code==200
    assert client.post(ep+"/decision",headers=owner,json={"action":"approve","revision":2}).status_code==200
    assert client.get(f"/api/content/{d['id']}").status_code==404
    assert client.get("/api/admin/editorial",headers=owner).status_code==403
    assert client.post(ep+"/decision",headers=owner,json={"action":"schedule","revision":3,"publish_at":"2099-01-01T00:00:00Z"}).status_code==200
    assert client.get(f"/api/content/{d['id']}").status_code==404
    assert client.post(ep+"/decision",headers=owner,json={"action":"cancel_schedule","revision":4}).status_code==200
    # Process a release deterministically without waiting for the background clock.
    import asyncio
    from app.db import db
    from app.routers.editorial import process_release
    assert client.post(ep+"/decision",headers=owner,json={"action":"schedule","revision":5,"publish_at":"2099-01-01T00:00:00Z"}).status_code==200
    async def release():
        row=await db.editorial_drafts.find_one({"id":d["id"]},{"_id":0})
        await process_release(row)
    asyncio.run(release())
    assert client.get(f"/api/content/{d['id']}").status_code==200
    assert client.get(preview.split("?")[0]).status_code==200
    row=client.get(root,headers=owner).json()[0]
    assert client.post(f"/api/admin/editorial/{d['id']}/suspend",headers=admin["h"],json={"action":"suspend","revision":row["revision"],"reason":"Review required"}).status_code==200
    asyncio.run(release())
    assert client.get(f"/api/content/{d['id']}").status_code==404
    assert client.get(preview.split("?")[0]).status_code==403
