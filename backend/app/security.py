from datetime import timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .db import db
from .util import now

bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": now() + timedelta(days=config.JWT_TTL_DAYS)},
                      config.JWT_SECRET, algorithm="HS256")


async def get_user_optional(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not creds:
        return None
    try:
        data = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return await db.users.find_one({"id": data.get("sub")}, {"_id": 0, "password_hash": 0})


def is_admin(user: dict | None) -> bool:
    return bool(user) and (user.get("role") == "admin" or user.get("email", "").lower() in config.ADMIN_EMAILS)


async def get_user(user=Depends(get_user_optional)):
    if not user:
        raise HTTPException(401, "Sign in to continue")
    if user.get("suspended"):
        raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
    return user


async def get_admin(user=Depends(get_user)):
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    return user
