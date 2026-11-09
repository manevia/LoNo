"""Pilot-mode bookkeeping: the moment the pilot started (staking stops accruing then)."""
from . import config
from .db import db
from .util import now_iso

_started: str | None = None


def pilot_started_at() -> str | None:
    return _started


async def init_pilot():
    """Fix the pilot start time once (from PILOT_STARTED_AT or the first start in pilot mode)."""
    global _started
    if not config.PILOT_MODE:
        return
    doc = await db.settings.find_one({"id": "pilot"})
    if config.PILOT_STARTED_AT:
        _started = config.PILOT_STARTED_AT
    elif doc:
        _started = doc["started_at"]
    else:
        _started = now_iso()
    await db.settings.update_one({"id": "pilot"}, {"$set": {"id": "pilot", "started_at": _started}}, upsert=True)
