"""Encrypt stream keys at rest and keep them out of logs and error messages."""
import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from .. import config


def _fernet() -> Fernet:
    raw = (config.SECRET_ENC_KEY or config.JWT_SECRET).encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"lono-stream-keys:" + raw).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def new_stream_key() -> str:
    return "lk_" + secrets.token_urlsafe(24)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def hint(key: str) -> str:
    return "…" + key[-4:] if len(key) >= 8 else "…"


def redact(text: str, *secret_values: str) -> str:
    """Remove secrets (and anything that looks like a URL-embedded key) from text."""
    out = text or ""
    for s in secret_values:
        if s and len(s) >= 4:
            out = out.replace(s, "••••")
    return out


def sign(value: str, ttl_tag: str = "") -> str:
    mac = hmac.new(config.JWT_SECRET.encode(), f"{value}|{ttl_tag}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac)[:22].decode()


def verify(value: str, sig: str, ttl_tag: str = "") -> bool:
    return hmac.compare_digest(sign(value, ttl_tag), sig or "")
