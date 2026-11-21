import asyncio
import uuid


def test_series_release_order_visibility_and_duplicates(client, user, admin):
    from app.db import db
    from app.routers.editorial import process_release

    h=user["h"]
    channel=client.get("/api/creator/profile",headers=h).json()["id"]
    root=f"/api/creator/editorial/{channel}"
    series_title="Series test "+uuid.uuid4().hex[:8]

    async def release(did):
        await process_release(await db.editorial_drafts.find_one({"id":did},{"_id":0}))

    def draft(season,episode,title,*,publish=False):
        body={"title":title,"kind":"series","category":"Education","episode":{"series_title":series_title,"season":season,"episode":episode,"runtime_minutes":25}}
        res=client.post(root,headers=h,json=body)
        assert res.status_code==200,res.text
        did=res.json()["id"];ep=f"{root}/{did}"
        asset=client.post(ep+"/assets",headers=h,files={"file":("episode.mp4",b"test media","video/mp4")}).json()
        body.update(media_id=asset["id"],revision=0)
        assert client.put(ep,headers=h,json=body).status_code==200
        if publish:
            for rev,action in [(1,"submit"),(2,"approve"),(3,"schedule")]:
                assert client.post(ep+"/decision",headers=h,json={"revision":rev,"action":action,"publish_at":"2099-01-01T00:00:00Z"}).status_code==200
        return did,ep

    first,_=draft(1,1,"First episode",publish=True)
    second,_=draft(1,2,"Second episode",publish=True)
    third,_=draft(2,1,"Second season premiere",publish=True)
    duplicate,_=draft(1,1,"Conflicting episode",publish=True)
    private,_=draft(1,3,"Unreleased episode")
    assert client.get(f"/api/content/{private}").status_code==404
    for did in (third,first,second,duplicate):asyncio.run(release(did))
    assert client.get(f"/api/content/{duplicate}").status_code==404
    row=client.get(f"/api/content/{first}").json()
    key=row["series"]["key"]
    assert row["next_episode"]["id"]==second
    assert row["previous_episode"] is None
    assert client.get(f"/api/content/{second}").json()["next_episode"]["id"]==third
    assert client.get(f"/api/content/{third}").json()["previous_episode"]["id"]==second
    listing=client.get("/api/series").json()["items"]
    card=next(x for x in listing if x["key"]==key)
    assert card["id"]==first and card["episodes"]==3 and sorted(card["seasons"])==[1,2]
    season=client.get(f"/api/series/{key}",params={"season":1}).json()
    assert season["seasons"]==[1,2]
    assert [e["id"] for e in season["items"]]==[first,second]
    assert all("stream_url" not in e for e in season["items"])
    d=next(x for x in client.get(root,headers=h).json() if x["id"]==second)
    assert client.post(f"/api/admin/editorial/{second}/suspend",headers=admin["h"],json={"action":"suspend","revision":d["revision"],"reason":"Test suspension"}).status_code==200
    asyncio.run(release(second))
    assert client.get(f"/api/content/{first}").json()["next_episode"]["id"]==third
