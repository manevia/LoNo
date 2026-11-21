from datetime import timedelta
from app.util import now
from test_course_builder import make_user


def test_channel_membership_role_isolation(client,user,admin):
    owner=user["h"]
    other=make_user(client); member=other["h"]
    # Use the registered account's email, not a bearer token or a shared login.
    me=client.get("/api/auth/me",headers=member).json()
    cid=client.get("/api/creator/profile",headers=owner).json()["id"]
    root=f"/api/creator/teams/{cid}"
    assert client.get(root+"/work",headers=member).status_code==404
    invite=client.post(root+"/invite",headers=owner,json={"email":me["email"],"role":"editor"})
    assert invite.status_code==200,invite.text
    mid=invite.json()["id"]
    assert client.get(root+"/work",headers=member).status_code==404
    assert client.post(f"/api/creator/teams/invitations/{mid}/accept",headers=admin["h"],json={"role":"editor"}).status_code==404
    assert client.post(f"/api/creator/teams/invitations/{mid}/accept",headers=member,json={"role":"editor"}).status_code==200
    assert client.get(root+"/members",headers=member).status_code==403
    assert client.post(root+"/work",headers=member,json={"kind":"programme","title":"Not allowed"}).status_code==403
    item=client.post(root+"/work",headers=member,json={"kind":"draft","title":"Editorial brief","notes":"Internal"})
    assert item.status_code==200,item.text
    review=root+f"/work/{item.json()['id']}/review"
    assert client.post(review,headers=member,json={"decision":"approved","feedback":"Approved","revision":0}).status_code==403
    assert client.post(review,headers=owner,json={"decision":"approved","feedback":"Approved","revision":0}).status_code==200
    assert client.put(root+f"/members/{mid}/role",headers=owner,json={"role":"producer"}).status_code==200
    s=client.put("/api/creator/stations/live_radio",headers=owner,json={"name":"Team radio"}).json()
    t=now()+timedelta(hours=1)
    ep=root+f"/stations/{s['id']}/programmes"
    assert client.post(ep,headers=member,json={"title":"Team programme","start":t.isoformat(),"end":(t+timedelta(hours=1)).isoformat()}).status_code==200
    assert client.post(root+f"/members/{mid}/revoke",headers=owner).status_code==200
    assert client.get(root+"/work",headers=member).status_code==404
    assert client.get("/api/auth/me",headers=member).json().get("is_admin") is not True
