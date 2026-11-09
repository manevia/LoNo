"""LMS: courses, lessons, quizzes, Learn-to-Earn and verifiable certificates.

Certificates carry a SHA-256 fingerprint of their contents. GET
/api/learn/certificates/{id} recomputes it, so anyone with the link can check a
certificate hasn't been altered. (On-chain anchoring is a later phase.)"""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config
from ..db import db
from ..ledger import credit
from ..security import get_user, get_user_optional
from ..util import now_iso, uid

router = APIRouter(prefix="/learn", tags=["learn"])


class QuizIn(BaseModel):
    answers: dict[str, int]


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=1000)


def _public(course: dict) -> dict:
    """Strip quiz answers before sending a course to the browser."""
    c = {k: v for k, v in course.items() if k != "_id"}
    quiz = c.get("quiz") or {}
    c["quiz"] = {"pass_mark": quiz.get("pass_mark", 0.7),
                 "questions": [{"id": q["id"], "prompt": q["prompt"], "options": q["options"]}
                               for q in quiz.get("questions", [])]}
    return c


PUBLISHED = {"status": {"$ne": "draft"}}  # seeded courses have no status field


def _progress(course: dict, enr: dict | None) -> dict:
    ids = [l["id"] for l in course.get("lessons", [])]
    total = len(ids)
    # Only count lessons that still exist; creators can edit a published course.
    completed = [i for i in (enr.get("completed_lessons", []) if enr else []) if i in ids]
    done = len(completed)
    return {"enrolled": bool(enr), "completed_lessons": completed,
            "lessons_done": done, "lessons_total": total,
            "percent": round(100 * done / total) if total else 0,
            "best_score": enr.get("best_score") if enr else None,
            "passed": bool(enr and enr.get("passed")),
            "certificate_id": enr.get("certificate_id") if enr else None}


def _fingerprint(cert: dict) -> str:
    body = {k: cert[k] for k in ("id", "user_id", "user_name", "course_id", "course_title", "score", "issued_at")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _course(course_id: str) -> dict:
    c = await db.courses.find_one({"id": course_id, **PUBLISHED}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Course not found")
    return c


@router.get("/courses")
async def courses(user=Depends(get_user_optional)):
    items = await db.courses.find(PUBLISHED, {"_id": 0}).to_list(200)
    enr = {}
    if user:
        async for e in db.enrollments.find({"user_id": user["id"]}, {"_id": 0}):
            enr[e["course_id"]] = e
    out = []
    for c in items:
        p = _public(c)
        p.pop("quiz")
        p["lessons"] = [{"id": l["id"], "title": l["title"], "duration_sec": l.get("duration_sec", 0)}
                        for l in c.get("lessons", [])]
        p["progress"] = _progress(c, enr.get(c["id"]))
        out.append(p)
    return out


@router.get("/courses/{course_id}")
async def course(course_id: str, user=Depends(get_user_optional)):
    c = await _course(course_id)
    enr = await db.enrollments.find_one({"user_id": user["id"], "course_id": course_id}) if user else None
    p = _public(c)
    p["progress"] = _progress(c, enr)
    return p


@router.post("/courses/{course_id}/enroll")
async def enroll(course_id: str, user=Depends(get_user)):
    c = await _course(course_id)
    if not await db.enrollments.find_one({"user_id": user["id"], "course_id": course_id}):
        await db.enrollments.insert_one({"id": uid(), "user_id": user["id"], "course_id": course_id,
                                         "completed_lessons": [], "attempts": [], "best_score": None,
                                         "passed": False, "certificate_id": None, "enrolled_at": now_iso()})
        await db.courses.update_one({"id": course_id}, {"$inc": {"enrolled": 1}})
    enr = await db.enrollments.find_one({"user_id": user["id"], "course_id": course_id})
    return _progress(c, enr)


@router.post("/courses/{course_id}/lessons/{lesson_id}/complete")
async def complete_lesson(course_id: str, lesson_id: str, user=Depends(get_user)):
    c = await _course(course_id)
    if lesson_id not in {l["id"] for l in c.get("lessons", [])}:
        raise HTTPException(404, "Lesson not found")
    res = await db.enrollments.update_one({"user_id": user["id"], "course_id": course_id},
                                          {"$addToSet": {"completed_lessons": lesson_id}})
    if not res.matched_count:
        raise HTTPException(400, "Enroll in the course first")
    enr = await db.enrollments.find_one({"user_id": user["id"], "course_id": course_id})
    return _progress(c, enr)


@router.post("/courses/{course_id}/quiz")
async def submit_quiz(course_id: str, body: QuizIn, user=Depends(get_user)):
    c = await _course(course_id)
    enr = await db.enrollments.find_one({"user_id": user["id"], "course_id": course_id})
    if not enr:
        raise HTTPException(400, "Enroll in the course first")
    if _progress(c, enr)["lessons_done"] < len(c.get("lessons", [])):
        raise HTTPException(400, "Finish every lesson before taking the quiz")
    qs = c["quiz"]["questions"]
    results = [{"id": q["id"], "correct": body.answers.get(q["id"]) == q["answer_index"]} for q in qs]
    score = round(sum(r["correct"] for r in results) / len(qs), 4) if qs else 0
    passed = score >= c["quiz"].get("pass_mark", 0.7)
    if passed or enr.get("passed"):  # reveal answers only once the reward can't be farmed
        for r, q in zip(results, qs):
            r.update(answer_index=q["answer_index"], explanation=q.get("explanation", ""))
    best = max(score, enr.get("best_score") or 0)
    await db.enrollments.update_one({"id": enr["id"]}, {
        "$push": {"attempts": {"score": score, "at": now_iso()}}, "$set": {"best_score": best}})

    reward, cert = 0.0, None
    if passed and not enr.get("passed"):
        # Atomic first-pass claim so rewards and certificates are issued exactly once.
        claim = await db.enrollments.update_one({"id": enr["id"], "passed": False}, {"$set": {"passed": True}})
        if claim.modified_count:
            cert = {"id": uid(), "user_id": user["id"], "user_name": user["name"], "course_id": c["id"],
                    "course_title": c["title"], "score": score, "issued_at": now_iso()}
            cert["fingerprint"] = _fingerprint(cert)
            await db.certificates.insert_one(dict(cert))
            await db.enrollments.update_one({"id": enr["id"]}, {"$set": {"certificate_id": cert["id"]}})
            own_course = c.get("owner_id") == user["id"]
            reward = 0.0 if own_course else float(c.get("reward_lono", 0))
            if reward > 0:
                await credit(user["id"], reward, "learn_to_earn", f"Passed: {c['title']}", ref=cert["id"])
            owner = c.get("owner_id")
            if owner and owner != "system" and not own_course and config.CREATOR_PAYOUT_PER_CERT > 0:
                await credit(owner, config.CREATOR_PAYOUT_PER_CERT, "creator_payout",
                             f"A learner passed: {c['title']}", ref=cert["id"])
            await db.courses.update_one({"id": c["id"]}, {"$inc": {"certificates_issued": 1}})
    return {"score": score, "passed": passed, "pass_mark": c["quiz"].get("pass_mark", 0.7),
            "results": results, "reward": reward, "certificate": cert,
            "certificate_id": (cert or {}).get("id") or enr.get("certificate_id")}


# ---------- reviews ----------
# Only learners who passed can review, so every rating comes from someone who
# finished the course. One review per learner; they can edit or delete it.

async def _refresh_rating(course: dict):
    total, count, dist = 0, 0, {str(i): 0 for i in range(1, 6)}
    async for r in db.reviews.find({"course_id": course["id"], "hidden": {"$ne": True}}, {"rating": 1}):
        total += r["rating"]
        count += 1
        dist[str(r["rating"])] += 1
    avg = round(total / count, 2) if count else None
    await db.courses.update_one({"id": course["id"]}, {"$set": {
        "rating_avg": avg, "rating_count": count, "rating_dist": dist}})
    if course.get("content_id"):  # catalogue cards show this rating too
        await db.content.update_one({"id": course["content_id"]}, {"$set": {"rating": round(avg, 1) if avg else None}})
    return {"average": avg, "count": count, "distribution": dist}


@router.get("/courses/{course_id}/reviews")
async def reviews(course_id: str, limit: int = 20, user=Depends(get_user_optional)):
    c = await _course(course_id)
    limit = max(1, min(limit, 100))
    items = await db.reviews.find({"course_id": course_id, "hidden": {"$ne": True}}, {"_id": 0}).sort("updated_at", -1).to_list(limit)
    mine = await db.reviews.find_one({"course_id": course_id, "user_id": user["id"]}, {"_id": 0}) if user else None
    can_review = False
    if user and c.get("owner_id") != user["id"]:
        enr = await db.enrollments.find_one({"user_id": user["id"], "course_id": course_id}, {"passed": 1})
        can_review = bool(enr and enr.get("passed"))
    for r in items:
        r.pop("user_id", None)
    return {"summary": {"average": c.get("rating_avg"), "count": c.get("rating_count", 0),
                        "distribution": c.get("rating_dist") or {str(i): 0 for i in range(1, 6)}},
            "items": items, "mine": mine, "can_review": can_review}


@router.put("/courses/{course_id}/review")
async def write_review(course_id: str, body: ReviewIn, user=Depends(get_user)):
    c = await _course(course_id)
    if c.get("owner_id") == user["id"]:
        raise HTTPException(400, "You can't review your own course")
    enr = await db.enrollments.find_one({"user_id": user["id"], "course_id": course_id}, {"passed": 1})
    if not (enr and enr.get("passed")):
        raise HTTPException(403, "Pass the course quiz to leave a review")
    existing = await db.reviews.find_one({"course_id": course_id, "user_id": user["id"]})
    doc = {"rating": body.rating, "text": body.text.strip(), "user_name": user["name"],
           "avatar_url": user.get("avatar_url"), "updated_at": now_iso()}
    if existing:
        await db.reviews.update_one({"id": existing["id"]}, {"$set": doc})
        rid = existing["id"]
    else:
        rid = uid()
        await db.reviews.insert_one({"id": rid, "course_id": course_id, "user_id": user["id"],
                                     "created_at": now_iso(), **doc})
    summary = await _refresh_rating(c)
    review = await db.reviews.find_one({"id": rid}, {"_id": 0, "user_id": 0})
    return {"review": review, "summary": summary}


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/reviews/{review_id}/report")
async def report_review(review_id: str, body: ReportIn, user=Depends(get_user)):
    r = await db.reviews.find_one({"id": review_id, "hidden": {"$ne": True}}, {"user_id": 1, "course_id": 1})
    if not r:
        raise HTTPException(404, "Review not found")
    if r["user_id"] == user["id"]:
        raise HTTPException(400, "You can't report your own review")
    if await db.reports.find_one({"target_id": review_id, "reporter_id": user["id"], "status": "open"}):
        return {"ok": True, "already_reported": True}
    await db.reports.insert_one({"id": uid(), "kind": "review", "target_id": review_id, "course_id": r["course_id"],
                                 "reporter_id": user["id"], "reason": body.reason.strip(), "status": "open",
                                 "created_at": now_iso()})
    return {"ok": True}


@router.delete("/courses/{course_id}/review")
async def delete_review(course_id: str, user=Depends(get_user)):
    c = await _course(course_id)
    res = await db.reviews.delete_one({"course_id": course_id, "user_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(404, "You haven't reviewed this course")
    return {"summary": await _refresh_rating(c)}


@router.get("/me")
async def my_learning(user=Depends(get_user)):
    certs = await db.certificates.find({"user_id": user["id"]}, {"_id": 0}).sort("issued_at", -1).to_list(100)
    enr = await db.enrollments.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    return {"enrollments": enr, "certificates": certs}


@router.get("/certificates/{cert_id}")
async def verify_certificate(cert_id: str):
    cert = await db.certificates.find_one({"id": cert_id}, {"_id": 0})
    if not cert:
        raise HTTPException(404, "No certificate with this ID")
    cert["valid"] = _fingerprint(cert) == cert.get("fingerprint")
    return cert
