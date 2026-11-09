"""Course builder for creators: drafts, editing, publish/unpublish.

Creators write lessons and quizzes; the platform sets the learner reward
(CREATOR_COURSE_REWARD) so nobody can mint $LONO by publishing a trivial course,
and the creator earns CREATOR_PAYOUT_PER_CERT each time someone else passes."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

import json
import re

from .. import ai, config
from ..db import db
from ..security import get_user
from ..util import now, now_iso, uid
from .creator import _channel_for

router = APIRouter(prefix="/creator/courses", tags=["course builder"])
MAX_LESSONS, MAX_QUESTIONS = 30, 30


class LessonIn(BaseModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=140)
    body: str = Field(default="", max_length=20000)
    video_url: str | None = Field(default=None, max_length=2000)
    duration_sec: int = Field(default=300, ge=0, le=6 * 3600)


class QuestionIn(BaseModel):
    id: str | None = None
    prompt: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    answer_index: int = Field(ge=0)
    explanation: str = Field(default="", max_length=1000)

    @field_validator("options")
    @classmethod
    def options_filled(cls, v):
        v = [o.strip() for o in v]
        if any(not o for o in v):
            raise ValueError("Every answer option needs text")
        if len(set(o.lower() for o in v)) != len(v):
            raise ValueError("Answer options must be different from each other")
        return v


class CourseIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)
    level: Literal["Beginner", "Intermediate", "Advanced"] = "Beginner"
    thumbnail_url: str = Field(default="", max_length=2000)
    lessons: list[LessonIn] = Field(default_factory=list, max_length=MAX_LESSONS)
    questions: list[QuestionIn] = Field(default_factory=list, max_length=MAX_QUESTIONS)
    pass_mark: float = Field(default=0.75, ge=0.5, le=1.0)


DEFAULT_THUMB = "https://images.unsplash.com/photo-1655947717064-d856af599bd1?crop=entropy&cs=srgb&fm=jpg&q=85"


def _problems(c: dict) -> list[str]:
    """What stops this course from being published, in plain words."""
    p = []
    if len(c.get("description", "").strip()) < 20:
        p.append("Add a description of at least 20 characters")
    if not c["lessons"]:
        p.append("Add at least one lesson")
    for i, l in enumerate(c["lessons"], 1):
        if not l.get("body", "").strip() and not l.get("video_url"):
            p.append(f"Lesson {i} needs some text or a video")
    qs = c["quiz"]["questions"]
    if len(qs) < 3:
        p.append("Add at least 3 quiz questions")
    for i, q in enumerate(qs, 1):
        if not 0 <= q["answer_index"] < len(q["options"]):
            p.append(f"Question {i}: mark which answer is correct")
    return p


def _view(c: dict) -> dict:
    out = {k: v for k, v in c.items() if k != "_id"}
    out["problems"] = _problems(c)
    return out


async def _own(course_id: str, user) -> dict:
    c = await db.courses.find_one({"id": course_id, "owner_id": user["id"]}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Course not found in your studio")
    return c


def _apply(body: CourseIn, existing: dict | None = None) -> dict:
    """Turn the editor payload into stored fields, keeping lesson/question ids stable
    so learners' progress survives edits."""
    for q in body.questions:
        if q.answer_index >= len(q.options):
            raise HTTPException(422, f"Question “{q.prompt[:40]}”: the correct answer must be one of its options")
    return {
        "title": body.title.strip(), "description": body.description.strip(), "level": body.level,
        "thumbnail_url": body.thumbnail_url.strip() or (existing or {}).get("thumbnail_url") or DEFAULT_THUMB,
        "lessons": [{"id": l.id or uid(), "title": l.title.strip(), "body": l.body.strip(),
                     "video_url": (l.video_url or "").strip() or None, "duration_sec": l.duration_sec}
                    for l in body.lessons],
        "quiz": {"pass_mark": body.pass_mark,
                 "questions": [{"id": q.id or uid(), "prompt": q.prompt.strip(), "options": q.options,
                                "answer_index": q.answer_index, "explanation": q.explanation.strip()}
                               for q in body.questions]},
        "updated_at": now_iso(),
    }


@router.get("")
async def my_courses(user=Depends(get_user)):
    items = await db.courses.find({"owner_id": user["id"]}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return [{"id": c["id"], "title": c["title"], "status": c.get("status", "published"), "level": c["level"],
             "thumbnail_url": c["thumbnail_url"], "lessons": len(c["lessons"]),
             "questions": len(c["quiz"]["questions"]), "enrolled": c.get("enrolled", 0),
             "certificates_issued": c.get("certificates_issued", 0), "updated_at": c.get("updated_at"),
             "rating_avg": c.get("rating_avg"), "rating_count": c.get("rating_count", 0),
             "ready": not _problems(c)} for c in items]


@router.post("")
async def create(body: CourseIn, user=Depends(get_user)):
    ch = await _channel_for(user)
    c = {"id": uid(), "owner_id": user["id"], "channel_id": ch["id"], "status": "draft", "content_id": None,
         "reward_lono": config.CREATOR_COURSE_REWARD, "enrolled": 0, "certificates_issued": 0,
         "created_at": now_iso(), **_apply(body)}
    await db.courses.insert_one(dict(c))
    return _view(c)


@router.get("/{course_id}")
async def get(course_id: str, user=Depends(get_user)):
    return _view(await _own(course_id, user))


@router.put("/{course_id}")
async def update(course_id: str, body: CourseIn, user=Depends(get_user)):
    c = await _own(course_id, user)
    fields = _apply(body, c)
    if c.get("status") == "published" and _problems({**c, **fields}):
        raise HTTPException(422, "A published course must stay complete: " + "; ".join(_problems({**c, **fields})))
    await db.courses.update_one({"id": course_id}, {"$set": fields})
    if c.get("content_id"):  # keep the catalogue entry in step
        await db.content.update_one({"id": c["content_id"]}, {"$set": {
            "title": fields["title"], "description": fields["description"],
            "thumbnail_url": fields["thumbnail_url"]}})
    return _view({**c, **fields})


@router.post("/{course_id}/publish")
async def publish(course_id: str, user=Depends(get_user)):
    c = await _own(course_id, user)
    problems = _problems(c)
    if problems:
        raise HTTPException(422, "Not ready to publish: " + "; ".join(problems))
    content_id = c.get("content_id")
    if not content_id:
        content_id = uid()
        await db.content.insert_one({
            "id": content_id, "title": c["title"], "description": c["description"], "kind": "course",
            "category": "Education", "thumbnail_url": c["thumbnail_url"],
            "stream_url": next((l["video_url"] for l in c["lessons"] if l.get("video_url")), ""),
            "duration_sec": sum(l["duration_sec"] for l in c["lessons"]), "is_original": False,
            "is_premium": False, "channel_id": c["channel_id"], "views": 0, "likes": 0, "rating": None,
            "year": now().year, "created_at": now_iso()})
    await db.courses.update_one({"id": course_id}, {"$set": {
        "status": "published", "content_id": content_id, "published_at": now_iso()}})
    return {"status": "published", "content_id": content_id, "url": f"/learn/{course_id}"}


@router.post("/{course_id}/unpublish")
async def unpublish(course_id: str, user=Depends(get_user)):
    c = await _own(course_id, user)
    if c.get("content_id"):
        await db.content.delete_one({"id": c["content_id"]})
    await db.courses.update_one({"id": course_id}, {"$set": {"status": "draft", "content_id": None}})
    return {"status": "draft"}


@router.delete("/{course_id}")
async def delete(course_id: str, user=Depends(get_user)):
    c = await _own(course_id, user)
    if c.get("certificates_issued", 0) > 0:
        raise HTTPException(400, "Learners hold certificates for this course. Unpublish it instead of deleting.")
    if c.get("content_id"):
        await db.content.delete_one({"id": c["content_id"]})
    await db.enrollments.delete_many({"course_id": course_id})
    await db.reviews.delete_many({"course_id": course_id})
    await db.courses.delete_one({"id": course_id})
    return {"ok": True}


class SuggestIn(BaseModel):
    count: int = Field(default=3, ge=1, le=8)


@router.post("/{course_id}/suggest-questions")
async def suggest_questions(course_id: str, body: SuggestIn, user=Depends(get_user)):
    """Claude drafts quiz questions from the saved lesson text. Nothing is stored:
    the creator reviews and edits them in the editor before saving."""
    c = await _own(course_id, user)
    material = "\n\n".join(f"## {l['title']}\n{l.get('body', '')}" for l in c["lessons"] if l.get("body"))
    if len(material) < 80:
        raise HTTPException(400, "Write some lesson text and save it first, so there's something to ask about")
    existing = [q["prompt"] for q in c["quiz"]["questions"]]
    raw = await ai.complete(
        "You write fair multiple-choice quiz questions for short online courses. Each question tests one idea "
        "stated in the lessons, has exactly one correct answer, and 3-4 plausible options. "
        "Reply with JSON only: a list of objects with keys prompt, options, answer_index, explanation.",
        [{"role": "user", "content": f"Course: {c['title']}\n\n{material[:12000]}\n\n"
                                     f"Avoid repeating these existing questions: {json.dumps(existing)}\n"
                                     f"Write {body.count} questions."}],
        max_tokens=1500)
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        items = json.loads(m.group(0) if m else raw)
        questions = [QuestionIn(**{k: q.get(k) for k in ("prompt", "options", "answer_index", "explanation") if q.get(k) is not None})
                     for q in items]
        questions = [q for q in questions if q.answer_index < len(q.options)]
    except Exception:
        raise HTTPException(502, "The AI's draft couldn't be read. Try again.")
    if not questions:
        raise HTTPException(502, "The AI didn't produce usable questions. Try again.")
    return {"questions": [q.model_dump(exclude={"id"}) for q in questions[: body.count]]}
