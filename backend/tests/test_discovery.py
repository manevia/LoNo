import asyncio
import uuid

from test_course_builder import make_user


def test_discovery_collections_and_opt_in_embed(client,user,admin):
    from app.db import db
    from app.routers.editorial import process_release
    h=user["h"]
    channel=client.get("/api/creator/profile",headers=h).json()["id"]
    root=f"/api/creator/editorial/{channel}"
    title="Discovery test "+uuid.uuid4().hex[:8]
    body={"title":title,"category":"Education","kind":"movie","film":{"format":"documentary","genres":["Rare genre"]}}
    draft=client.post(root,headers=h,json=body).json();cid=draft["id"];ep=f"{root}/{cid}"
    asset=client.post(ep+"/assets",headers=h,files={"file":("video.mp4",b"sample","video/mp4")}).json()
    body.update(media_id=asset["id"],revision=0)
    assert client.put(ep,headers=h,json=body).status_code==200
    search=lambda:client.get("/api/discovery/search",params={"q":title}).json()["items"]
    url=f"/api/discovery/embed/{cid}"
    assert search()==[] and client.get(url).status_code==404
    for rev,action in [(1,"submit"),(2,"approve"),(3,"schedule")]:
        assert client.post(ep+"/decision",headers=h,json={"revision":rev,"action":action,"publish_at":"2099-01-01T00:00:00Z"}).status_code==200
    async def release():
        await process_release(await db.editorial_drafts.find_one({"id":cid},{"_id":0}))
    asyncio.run(release())
    assert [r["id"] for r in search()]==[cid]
    assert all("stream_url" not in r for r in search())
    lite=client.get("/api/discovery/search",params={"q":"Rare genre","kind":"movie","lite":True}).json()["items"]
    assert any(r["id"]==cid and r["thumbnail_url"]=="" for r in lite)
    assert client.get(url).status_code==404
    settings=f"/api/discovery/creator/{channel}/{cid}"
    other=make_user(client)["h"]
    assert client.put(settings,headers=other,json={"enabled":True}).status_code==404
    assert client.put(settings,headers=h,json={"enabled":True}).status_code==200
    player=client.get(url)
    assert player.status_code==200 and "<video" in player.text and "<script" not in player.text
    assert "frame-ancestors" in player.headers["content-security-policy"]
    assert "x-frame-options" not in player.headers
    assert client.get("/api/discovery/search").headers["x-frame-options"]=="DENY"
    collection={"title":"Featured test","items":[cid],"featured":True}
    assert client.post("/api/discovery/admin/collections",headers=h,json=collection).status_code==403
    r=client.post("/api/discovery/admin/collections",headers=admin["h"],json=collection)
    assert r.status_code==200
    key=r.json()["id"]
    assert any(x["key"]==key for x in client.get("/api/discovery/highlights").json())
    assert client.put(settings,headers=h,json={"enabled":False}).status_code==200
    assert client.get(url).status_code==404
    d=next(x for x in client.get(root,headers=h).json() if x["id"]==cid)
    assert client.post(f"/api/admin/editorial/{cid}/suspend",headers=admin["h"],json={"action":"suspend","revision":d["revision"],"reason":"Test suspension"}).status_code==200
    asyncio.run(release())
    assert search()==[] and not any(x["key"]==key for x in client.get("/api/discovery/highlights").json())
