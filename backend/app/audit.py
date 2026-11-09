"""Append-only audit log for compliance: consents, data requests, account
deletions and admin actions. Entries never store a deleted person's email in
plain text, only a SHA-256 hash, so a request can be evidenced without keeping
the data that was erased."""
import hashlib

from .db import db
from .util import now_iso, uid


def email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


async def audit(action: str, actor: dict | None = None, target: str | None = None,
                details: dict | None = None, subject_email: str | None = None):
    entry = {"id": uid(), "at": now_iso(), "action": action,
             "actor_id": (actor or {}).get("id"), "actor_name": (actor or {}).get("name"),
             "target": target, "details": details or {}}
    if subject_email:
        entry["subject_email_hash"] = email_hash(subject_email)
    await db.audit_log.insert_one(entry)
    entry.pop("_id", None)
    return entry
