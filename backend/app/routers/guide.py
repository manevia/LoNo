"""Live TV and radio program guide (EPG).

Schedules are generated deterministically from each channel's category, so every
viewer sees the same guide and it stays stable through the day. When real
schedules exist (a "schedule" list on the channel's content document with
start/end/title/description), those are used instead."""
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from ..db import db
from ..util import now

router = APIRouter(prefix="/live", tags=["live"])
SLOT_MIN = 30

POOLS = {
    "News": [("Morning Briefing", "Headlines from Monrovia and around the world."),
             ("Africa Today", "Politics, business and people across the continent."),
             ("The Midday Report", "Live updates and analysis."),
             ("World Desk", "International news and correspondents' reports."),
             ("Business Hour", "Markets, trade and the economy."),
             ("Newsnight", "The day's stories in depth.")],
    "Sports": [("Matchday Live", "Live commentary from today's fixtures."),
               ("Football Focus", "Previews, analysis and interviews."),
               ("The Locker Room", "Players and coaches in conversation."),
               ("Highlights Show", "Every goal, every key moment."),
               ("Athletics Weekly", "Track, field and road running.")],
    "Movies": [("Classic Matinee", "A restored classic from the archive."),
               ("Director's Cut", "An acclaimed film, introduced by critics."),
               ("Late Night Feature", "Cult favourites after dark."),
               ("Family Cinema", "Films for all ages.")],
    "Culture": [("Studio Session", "Live music recorded in our studio."),
                ("The Interview", "Artists, writers and thinkers."),
                ("Market Day", "Food, craft and street life."),
                ("Gallery Walk", "Exhibitions and the people behind them.")],
    "Talk": [("Open Line", "Your calls on the day's big question."),
             ("Breakfast Talk", "News, weather and conversation."),
             ("The Debate", "Two sides, one microphone."),
             ("Community Voices", "Local stories from across the country.")],
    "Music": [("Morning Mix", "Upbeat tracks to start the day."),
              ("Indie Hour", "New independent releases."),
              ("Afrobeats Now", "The latest from West Africa and beyond."),
              ("Night Drive", "Synthwave and downtempo after dark."),
              ("Request Show", "Your requests, on air.")],
    "Interview": [("In Conversation", "A long-form interview."),
                  ("Life Stories", "Ordinary people, extraordinary lives."),
                  ("The Founders", "How builders started out.")],
}
DEFAULT_POOL = [("Live Programming", "Live on the LoNo network."), ("Studio Hour", "From the studio."),
                ("Special Feature", "Something different.")]


def _h(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _schedule(channel: dict, start: datetime, end: datetime) -> list[dict]:
    if channel.get("schedule"):
        return [p for p in channel["schedule"] if p["end"] > start.isoformat() and p["start"] < end.isoformat()]
    pool = POOLS.get(channel.get("category"), DEFAULT_POOL)
    # Programs start on the half hour. Walk from the start of the day so slots are stable.
    t = start.replace(hour=0, minute=0, second=0, microsecond=0)
    out, i = [], 0
    while t < end:
        length = SLOT_MIN * (1 + _h(channel["id"], t.date(), i) % 2)  # 30 or 60 minutes
        title, desc = pool[_h(channel["id"], t.isoformat()) % len(pool)]
        e = t + timedelta(minutes=length)
        if e > start:
            out.append({"start": t.isoformat(), "end": e.isoformat(), "title": title, "description": desc})
        t, i = e, i + 1
    return out


async def _channels():
    tv = await db.content.find({"kind": "live_tv"}, {"_id": 0, "subtitles_vtt": 0, "transcript": 0}).to_list(200)
    radio = await db.content.find({"kind": "live_radio"}, {"_id": 0, "subtitles_vtt": 0, "transcript": 0}).to_list(200)
    # Stable numbering: oldest channels keep the low numbers, new ones are added at the end.
    for group in (tv, radio):
        group.sort(key=lambda c: (c.get("created_at", ""), c["title"]))
        for n, c in enumerate(group, 1):
            c["number"] = n
    return tv, radio


@router.get("/guide")
async def guide(hours: int = 4):
    hours = max(1, min(hours, 24))
    t = now()
    start = t.replace(minute=0 if t.minute < 30 else 30, second=0, microsecond=0)
    end = start + timedelta(hours=hours)
    tv, radio = await _channels()
    for c in tv + radio:
        c["programs"] = _schedule(c, start, end)
        cur = [p for p in c["programs"] if p["start"] <= t.isoformat() < p["end"]]
        c["now"] = cur[0] if cur else None
        later = [p for p in c["programs"] if p["start"] > t.isoformat()]
        c["next"] = later[0] if later else None
    return {"start": start.isoformat(), "end": end.isoformat(), "now": t.isoformat(),
            "slot_minutes": SLOT_MIN, "tv": tv, "radio": radio}
