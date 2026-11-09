"""Account self-service: profile edits, password, data export and deletion.

Export and deletion cover the GDPR rights of access (Art. 15/20) and erasure
(Art. 17). Deletion removes the person's data; aggregate counts they contributed
to (votes, views, subscriber totals) stay, without any link back to them."""
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..db import db
from ..security import check_password, get_user, hash_password
from ..storage import storage
from ..util import now_iso, today, uid

router = APIRouter(tags=["account"])


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=2000)


class PasswordIn(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=128)


class DeleteIn(BaseModel):
    confirm_email: str
    password: str | None = None


async def _full_user(user_id: str) -> dict:
    return await db.users.find_one({"id": user_id})


def _verify_password(u: dict, password: str | None):
    if u.get("password_hash") and not (password and check_password(password, u["password_hash"])):
        raise HTTPException(400, "Your current password is incorrect")


@router.patch("/auth/me")
async def update_profile(body: ProfileIn, user=Depends(get_user)):
    changes = {k: v.strip() for k, v in body.model_dump(exclude_none=True).items()}
    if changes:
        await db.users.update_one({"id": user["id"]}, {"$set": changes})
        if "name" in changes:  # keep the name on their reviews in step
            await db.reviews.update_many({"user_id": user["id"]}, {"$set": {"user_name": changes["name"]}})
    return await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})


@router.post("/auth/password")
async def change_password(body: PasswordIn, user=Depends(get_user)):
    """Change a password, or set one for an account created with Google."""
    u = await _full_user(user["id"])
    _verify_password(u, body.current_password)
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password),
                                                            "password_changed_at": now_iso()}})
    return {"ok": True}


async def _collect(user_id: str) -> dict:
    no_id = {"_id": 0}
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    channel = await db.channels.find_one({"owner_id": user_id}, no_id)
    content = await db.content.find({"channel_id": channel["id"]}, {"_id": 0, "subtitles_vtt": 0}).to_list(1000) if channel else []
    return {
        "exported_at": now_iso(),
        "about": "Everything LoNo stores about your account. $LONO is a simulated in-app token with no cash value.",
        "account": u,
        "transactions": await db.transactions.find({"user_id": user_id}, no_id).sort("at", 1).to_list(100000),
        "stakes": await db.stakes.find({"user_id": user_id}, no_id).to_list(1000),
        "watch_sessions": await db.watch_sessions.find({"user_id": user_id}, no_id).to_list(100000),
        "votes": await db.votes.find({"user_id": user_id}, no_id).to_list(1000),
        "proposals": await db.proposals.find({"author_id": user_id}, no_id).to_list(1000),
        "enrollments": await db.enrollments.find({"user_id": user_id}, no_id).to_list(1000),
        "certificates": await db.certificates.find({"user_id": user_id}, no_id).to_list(1000),
        "reviews": await db.reviews.find({"user_id": user_id}, no_id).to_list(1000),
        "ai_conversations": await db.ai_sessions.find({"user_id": user_id}, no_id).to_list(1000),
        "uploaded_files": await db.files.find({"user_id": user_id}, no_id).to_list(10000),
        "channel": channel,
        "channel_content": content,
        "courses_created": await db.courses.find({"owner_id": user_id}, no_id).to_list(1000),
    }


@router.get("/me/export")
async def export(user=Depends(get_user)):
    data = await _collect(user["id"])
    buf = io.BytesIO(json.dumps(data, indent=2, ensure_ascii=False, default=str).encode())
    return StreamingResponse(buf, media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="lono-data-{today()}.json"'})


@router.delete("/me")
async def delete_account(body: DeleteIn, user=Depends(get_user)):
    u = await _full_user(user["id"])
    if body.confirm_email.strip().lower() != u["email"]:
        raise HTTPException(400, "Type your account's email address exactly to confirm")
    _verify_password(u, body.password)
    uid_ = u["id"]

    # Creator data: channel, uploads, courses (learners elsewhere keep their certificates,
    # which store the course title and their own name).
    channel = await db.channels.find_one({"owner_id": uid_})
    if channel:
        await db.content.delete_many({"channel_id": channel["id"]})
        await db.channels.delete_one({"id": channel["id"]})
    async for c in db.courses.find({"owner_id": uid_}, {"id": 1}):
        await db.enrollments.delete_many({"course_id": c["id"]})
        await db.reviews.delete_many({"course_id": c["id"]})
    await db.courses.delete_many({"owner_id": uid_})
    async for f in db.files.find({"user_id": uid_}, {"storage_path": 1}):
        try:
            await storage.delete(f["storage_path"])
        except Exception:
            pass  # storage outage shouldn't block erasure; the record goes either way
    await db.files.delete_many({"user_id": uid_})

    # Their reviews go, and the ratings they fed are recomputed.
    affected = [r["course_id"] async for r in db.reviews.find({"user_id": uid_}, {"course_id": 1})]
    await db.reviews.delete_many({"user_id": uid_})
    from .learn import _refresh_rating
    for cid in set(affected):
        c = await db.courses.find_one({"id": cid})
        if c:
            await _refresh_rating(c)

    # Subscriber counts drop for the channels they followed.
    for ch in u.get("subscribed_channels", []):
        await db.channels.update_one({"id": ch}, {"$inc": {"subscribers": -1}})

    for coll in ("transactions", "stakes", "enrollments", "certificates", "ai_sessions"):
        await db[coll].delete_many({"user_id": uid_})
    # Keep aggregate tallies honest without a link to the person.
    # A fresh random id per deleted account keeps the one-vote-per-person index valid.
    await db.votes.update_many({"user_id": uid_}, {"$set": {"user_id": f"deleted-{uid()}"}})
    await db.watch_sessions.update_many({"user_id": uid_}, {"$set": {"user_id": None}})
    await db.proposals.update_many({"author_id": uid_}, {"$set": {"author_id": None, "author_name": "Former member"}})
    await db.users.delete_one({"id": uid_})
    return {"ok": True, "deleted_at": now_iso()}
