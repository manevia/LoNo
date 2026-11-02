from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import ai
from ..db import db
from ..security import get_user, get_user_optional
from ..storage import storage
from ..util import now_iso, uid

router = APIRouter(prefix="/ai", tags=["ai"])
HISTORY_TURNS = 20


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class SummarizeIn(BaseModel):
    content_id: str


async def _catalogue_brief() -> str:
    rows = await db.content.find({}, {"_id": 0, "title": 1, "kind": 1, "category": 1}).limit(60).to_list(60)
    return "\n".join(f"- {r['title']} ({r['kind'].replace('_', ' ')}, {r['category']})" for r in rows)


@router.post("/chat")
async def chat(body: ChatIn, user=Depends(get_user_optional)):
    sid = body.session_id or uid()
    owner = user["id"] if user else None
    sess = await db.ai_sessions.find_one({"id": sid})
    if sess and sess.get("user_id") != owner:
        sess, sid = None, uid()  # never resume someone else's conversation
    history = (sess or {}).get("messages", [])[-HISTORY_TURNS:]
    system = (
        "You are LoNo AI, the assistant inside LoNo, a platform for streaming TV, radio, podcasts, "
        "music and courses, with creator channels and a simulated utility token called $LONO. "
        "Viewers earn $LONO by watching (verified minutes, daily cap) and by passing course quizzes; "
        "they can stake it for 30/90/180/365 days (8/14/22/35% APY) and vote on DAO proposals. "
        "$LONO is an in-app ledger with no cash value; never give investment advice. "
        "Be concise and friendly. When recommending, only name titles from this catalogue:\n"
        + await _catalogue_brief()
    )
    if user:
        system += f"\nThe user is {user['name']} on the {user.get('plan', 'free')} plan."
    messages = history + [{"role": "user", "content": body.message}]
    reply = await ai.complete(system, messages)
    messages.append({"role": "assistant", "content": reply})
    await db.ai_sessions.update_one(
        {"id": sid}, {"$set": {"id": sid, "user_id": owner, "messages": messages[-HISTORY_TURNS * 2:],
                               "updated_at": now_iso()}}, upsert=True)
    return {"reply": reply, "session_id": sid}


@router.post("/summarize")
async def summarize(body: SummarizeIn):
    c = await db.content.find_one({"id": body.content_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Title not found")
    if c.get("ai_summary"):
        return {"summary": c["ai_summary"], "cached": True}
    extra = f"\nTranscript excerpt: {c['transcript'][:3000]}" if c.get("transcript") else ""
    text = await ai.complete(
        "You write short, spoiler-free synopses and SEO tags for a streaming catalogue.",
        [{"role": "user", "content":
          f"Title: {c['title']}\nType: {c['kind']}\nCategory: {c['category']}\n"
          f"Description: {c['description']}{extra}\n\n"
          "Write a 3-sentence synopsis, then a final line starting 'Tags:' with 5 comma-separated tags."}],
        max_tokens=400)
    await db.content.update_one({"id": c["id"]}, {"$set": {"ai_summary": text}})
    return {"summary": text, "cached": False}


@router.get("/recommend")
async def recommend(user=Depends(get_user)):
    ids = [h["content_id"] for h in user.get("watch_history", [])][:20] + user.get("liked", [])
    watched = await db.content.find({"id": {"$in": ids}}, {"_id": 0, "category": 1}).to_list(40)
    cats = list({w["category"] for w in watched}) or ["Drama", "Documentary", "Education"]
    recs = await db.content.find({"category": {"$in": cats}, "id": {"$nin": ids}},
                                 {"_id": 0, "subtitles_vtt": 0, "transcript": 0}).limit(12).to_list(12)
    return {"based_on": cats, "items": recs}


@router.post("/transcribe/{content_id}")
async def transcribe(content_id: str, user=Depends(get_user)):
    import httpx
    c = await db.content.find_one({"id": content_id})
    if not c:
        raise HTTPException(404, "Title not found")
    if c.get("subtitles_vtt"):
        return {"vtt": c["subtitles_vtt"], "text": c.get("transcript", ""), "cached": True}
    src = c.get("stream_url") or ""
    if src.startswith("/api/files/"):
        key = src.split("/api/files/", 1)[1]
        rec = await db.files.find_one({"storage_path": key})
        data, ct = await storage.read(key), (rec or {}).get("content_type", "video/mp4")
    else:
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as hc:
                r = await hc.get(src, headers={"User-Agent": "LoNoBot/2.0"})
                r.raise_for_status()
                data, ct = r.content, r.headers.get("content-type", "audio/mpeg")
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Couldn't fetch the media file: {e}")
    result = await ai.transcribe(data, ct)
    vtt = ai.to_vtt(result)
    await db.content.update_one({"id": content_id}, {"$set": {
        "subtitles_vtt": vtt, "transcript": result.get("text", ""), "subtitle_lang": result.get("language", "en")}})
    return {"vtt": vtt, "text": result.get("text", ""), "cached": False}
