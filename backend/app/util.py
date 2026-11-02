import uuid
from datetime import datetime, timezone


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def today() -> str:
    return now().strftime("%Y-%m-%d")


def clean(doc):
    """Drop Mongo's _id and secrets before returning a document."""
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc
