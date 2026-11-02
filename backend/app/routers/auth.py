import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from .. import config
from ..db import db
from ..ledger import credit, new_wallet
from ..security import check_password, get_user, hash_password, make_token
from ..util import clean, now_iso, uid

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleIn(BaseModel):
    credential: str  # ID token from Google Identity Services


async def create_user(email: str, name: str, provider: str, password: str | None = None,
                      avatar_url: str | None = None) -> dict:
    user_id = uid()
    doc = {
        "id": user_id, "email": email.lower(), "name": name.strip(),
        "avatar_url": avatar_url or f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_id}",
        "role": "viewer", "provider": provider, "plan": "free", "created_at": now_iso(),
        "wallet": new_wallet(), "watch_history": [], "subscribed_channels": [],
        "liked": [], "my_list": [],
    }
    if password:
        doc["password_hash"] = hash_password(password)
    await db.users.insert_one(doc)
    if config.SIGNUP_BONUS > 0:
        await credit(user_id, config.SIGNUP_BONUS, "signup_bonus", "Welcome bonus")
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


@router.post("/register")
async def register(body: RegisterIn):
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(400, "That email already has an account. Sign in instead.")
    user = await create_user(body.email, body.name, "email", password=body.password)
    return {"token": make_token(user["id"]), "user": user}


@router.post("/login")
async def login(body: LoginIn):
    u = await db.users.find_one({"email": body.email.lower()})
    if not u or not u.get("password_hash") or not check_password(body.password, u["password_hash"]):
        raise HTTPException(400, "Email or password is incorrect")
    return {"token": make_token(u["id"]), "user": clean(u)}


@router.post("/google")
async def google(body: GoogleIn):
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is off. Set GOOGLE_CLIENT_ID on the server.")
    async with httpx.AsyncClient(timeout=10) as hc:
        r = await hc.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": body.credential})
    if r.status_code != 200:
        raise HTTPException(401, "Google sign-in could not be verified")
    info = r.json()
    if info.get("aud") != config.GOOGLE_CLIENT_ID or info.get("email_verified") not in ("true", True):
        raise HTTPException(401, "Google sign-in could not be verified")
    email = info["email"].lower()
    u = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not u:
        u = await create_user(email, info.get("name") or email.split("@")[0], "google",
                              avatar_url=info.get("picture"))
    return {"token": make_token(u["id"]), "user": u}


@router.get("/me")
async def me(user=Depends(get_user)):
    return user
