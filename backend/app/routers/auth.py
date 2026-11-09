import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from .. import config
from ..db import db
from ..ledger import credit, new_wallet
from ..ratelimit import RateLimiter, client_ip
from ..audit import audit
from ..security import check_password, get_user, hash_password, is_admin, make_token
from ..util import clean, now_iso, uid

router = APIRouter(prefix="/auth", tags=["auth"])

login_failures = RateLimiter(config.LOGIN_MAX_FAILURES, config.LOGIN_WINDOW_SEC,
                             "Too many failed sign-in attempts.")
signups = RateLimiter(config.SIGNUPS_PER_IP_PER_HOUR, 3600, "Too many new accounts from this network.")


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    accept_terms: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleIn(BaseModel):
    credential: str  # ID token from Google Identity Services


async def create_user(email: str, name: str, provider: str, password: str | None = None,
                      avatar_url: str | None = None, record_consent: bool = True) -> dict:
    user_id = uid()
    consent = {"type": "terms", "version": config.TERMS_VERSION, "at": now_iso(), "method": provider}
    doc = {
        "id": user_id, "email": email.lower(), "name": name.strip(),
        "avatar_url": avatar_url or f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_id}",
        "role": "viewer", "provider": provider, "plan": "free", "created_at": now_iso(),
        "wallet": new_wallet(), "watch_history": [], "subscribed_channels": [],
        "liked": [], "my_list": [], "consents": [consent] if record_consent else [],
    }
    if password:
        doc["password_hash"] = hash_password(password)
    await db.users.insert_one(doc)
    if config.SIGNUP_BONUS > 0:
        await credit(user_id, config.SIGNUP_BONUS, "signup_bonus", "Welcome bonus")
    await audit("account_created", {"id": user_id, "name": name.strip()}, target=user_id,
                details={"provider": provider, "terms_version": config.TERMS_VERSION if record_consent else None})
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


@router.post("/register")
async def register(body: RegisterIn, request: Request):
    if not body.accept_terms:
        raise HTTPException(400, "Please accept the Terms and the $LONO disclosure to create an account")
    ip = client_ip(request)
    signups.check(ip)
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(400, "That email already has an account. Sign in instead.")
    user = await create_user(body.email, body.name, "email", password=body.password)
    signups.hit(ip)
    return {"token": make_token(user["id"]), "user": await me_view(user)}


@router.post("/login")
async def login(body: LoginIn, request: Request):
    # Keyed on email+IP: an attacker can't lock a real user out from elsewhere,
    # and one IP can't hammer one account.
    key = f"{body.email.lower()}|{client_ip(request)}"
    login_failures.check(key)
    u = await db.users.find_one({"email": body.email.lower()})
    if not u or not u.get("password_hash") or not check_password(body.password, u["password_hash"]):
        login_failures.hit(key)
        raise HTTPException(400, "Email or password is incorrect")
    login_failures.reset(key)
    if u.get("suspended"):
        raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
    return {"token": make_token(u["id"]), "user": await me_view(u)}


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
    if u.get("suspended"):
        raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
    return {"token": make_token(u["id"]), "user": await me_view(u)}


async def me_view(user: dict) -> dict:
    """The signed-in user as the app sees it. Login, sign-up, Google and /me all return
    this, so flags like is_admin and needs_terms are right straight after signing in."""
    user = clean(user)
    has_pw = await db.users.count_documents({"id": user["id"], "password_hash": {"$exists": True}})
    accepted = any(c.get("type") == "terms" and c.get("version") == config.TERMS_VERSION
                   for c in user.get("consents", []))
    return {**user, "has_password": bool(has_pw), "is_admin": is_admin(user),
            "terms_version": config.TERMS_VERSION, "needs_terms": not accepted}


@router.get("/me")
async def me(user=Depends(get_user)):
    return await me_view(user)


@router.post("/accept-terms")
async def accept_terms(user=Depends(get_user)):
    """Record consent to the current terms (existing users after the terms change)."""
    consent = {"type": "terms", "version": config.TERMS_VERSION, "at": now_iso(), "method": "prompt"}
    await db.users.update_one({"id": user["id"]}, {"$push": {"consents": consent}})
    await audit("terms_accepted", user, target=user["id"], details={"terms_version": config.TERMS_VERSION})
    return {"ok": True, "version": config.TERMS_VERSION}
