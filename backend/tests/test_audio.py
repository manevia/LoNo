import asyncio
import uuid

from test_course_builder import make_user


def test_audio_release_catalogue_and_private_playlist(client,user,admin):
    from app.db import db
    from app.routers.editorial import process_release
    h=user["h"]
    channel=client.get("/api/creator/profile",headers=h).json()["id"]
    root=f"/api/creator/editorial/{channel}"
    artist="Artist "+uuid.uuid4().hex[:8]

    async def release(did):
        await process_release(await db.editorial_drafts.find_one({"id":did},{"_id":0}))

    def draft(kind,track,season=1,publish=True):
        metadata={"artist":artist,"artist_bio":"Audio creator","release_type":"album" if kind=="music" else "podcast","collection_title":"First collection","track":track,"season":season,"runtime_minutes":3}
        body={"title":f"{kind} S{season} T{track}","category":"General","kind":kind,"audio":metadata}
        res=client.post(root,headers=h,json=body)
        assert res.status_code==200,res.text
        did=res.json()["id"];ep=f"{root}/{did}"
        asset=client.post(ep+"/assets",headers=h,files={"file":("audio.mp3",b"sample","audio/mpeg")}).json()
        body.update(media_id=asset["id"],revision=0)
        assert client.put(ep,headers=h,json=body).status_code==200
        if publish:
            for rev,action in [(1,"submit"),(2,"approve"),(3,"schedule")]:
                assert client.post(ep+"/decision",headers=h,json={"revision":rev,"action":action,"publish_at":"2099-01-01T00:00:00Z"}).status_code==200
        return did

    first=draft("music",1);second=draft("music",2);duplicate=draft("music",1);private=draft("music",3,publish=False)
    podcast=draft("podcast",1);podcast2=draft("podcast",1,2)
    assert client.get(f"/api/content/{private}").status_code==404
    for did in (second,first,duplicate,podcast,podcast2):asyncio.run(release(did))
    assert client.get(f"/api/content/{duplicate}").status_code==404
    row=client.get(f"/api/content/{first}").json()
    assert row["next_audio"]["id"]==second and row["duration_sec"]==180
    key=row["audio"]["collection_key"]
    cards=client.get("/api/audio/catalogue",params={"kind":"music"}).json()["items"]
    card=next(c for c in cards if c["key"]==key)
    assert card["count"]==2 and card["id"]==first
    tracks=client.get(f"/api/audio/collection/{key}").json()["items"]
    assert [x["id"] for x in tracks]==[first,second]
    assert all("stream_url" not in x for x in tracks)
    profile=client.get(f"/api/audio/artist/{row['audio']['artist_key']}").json()
    assert profile["name"]==artist
    assert client.get(f"/api/content/{podcast}").json()["next_audio"]["id"]==podcast2
    assert client.post("/api/audio/playlists",headers=h,json={"name":"Private only","items":[private]}).status_code==422
    p=client.post("/api/audio/playlists",headers=h,json={"name":"My audio","items":[second,first]}).json()
    assert [x["id"] for x in p["items"]]==[second,first]
    other=make_user(client)["h"]
    assert client.get("/api/audio/playlists",headers=other).json()==[]
    assert client.put(f"/api/audio/playlists/{p['id']}",headers=other,json={"name":"No","items":[]}).status_code==404
    assert client.delete(f"/api/audio/playlists/{p['id']}",headers=other).status_code==404
    d=next(x for x in client.get(root,headers=h).json() if x["id"]==second)
    assert client.post(f"/api/admin/editorial/{second}/suspend",headers=admin["h"],json={"action":"suspend","revision":d["revision"],"reason":"Test suspension"}).status_code==200
    asyncio.run(release(second))
    p=client.get("/api/audio/playlists",headers=h).json()[0]
    assert [x["id"] for x in p["items"]]==[first] and p["unavailable"]==1
