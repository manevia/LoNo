def test_creator_verification_and_private_fields(client,user,admin):
    h=user["h"]
    first=client.get("/api/creator/profile",headers=h).json()
    cid=first["id"]
    assert client.get("/api/admin/creators",headers=h).status_code==403
    assert client.post("/api/creator/verification/submit",headers=h).status_code==422
    profile={"classification":"university","organization":"Example University","country":"Liberia","website":"https://example.org","verification_note":"Private review information"}
    assert client.put("/api/creator/profile",headers=h,json=profile).status_code==200
    result=client.post("/api/creator/verification/submit",headers=h).json()
    assert result["verification_status"]=="pending"
    assert client.post("/api/creator/verification/submit",headers=h).status_code==409
    public=client.get(f"/api/channels/{cid}").json()
    assert "creator_profile" not in public and "verification_reason" not in public
    assert client.post(f"/api/admin/creators/{cid}/review",headers=h,json={"decision":"verified","reason":"Invalid self approval","revision":result["creator_revision"]}).status_code==403
    assert client.post(f"/api/admin/creators/{cid}/review",headers=admin["h"],json={"decision":"verified","reason":"Reviewed public affiliation","revision":result["creator_revision"]}).status_code==200
    assert client.get(f"/api/channels/{cid}").json()["verification_status"]=="verified"
    bad={"name":"New name","avatar_url":"javascript:alert(1)"}
    assert client.put("/api/creator/channel",headers=h,json=bad).status_code==422
    renamed=client.put("/api/creator/channel",headers=h,json={"name":"New channel name"}).json()
    assert renamed["id"]==cid and renamed["handle"]==first["handle"] and renamed["verification_status"]=="unverified"
