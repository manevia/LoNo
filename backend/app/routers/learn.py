"""LMS: courses, lessons, quizzes, Learn-to-Earn and verifiable certificates.

Certificates carry a SHA-256 fingerprint of their contents. GET
/api/learn/certificates/{id} recomputes it, so anyone with the link can check a
certificate hasn't been altered. (On-chain anchoring is a later phase.)"""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import db
from ..ledger import credit
from ..security import get_user, get_user_optional
from ..util import now_iso, uid

router = APIRouter(prefix="/learn", tags=["learn"])


class QuizIn(BaseModel):
    answers: dict[str, int]


def _public(course: dict) -> dict:
    """Strip quiz answers before sending a course to the browser."""
    c = {k: v for k, v in course.items() if k != "_id"}
    quiz = c.get("quiz") or {}
    c["quiz"] = {"pass_mark": quiz.get("pass_mark", 0.7),
                 "questions": [{"id": q["id"], "prompt": q["prompt"], "options": q["options"]}
                               for q in quiz.get("questions", [])]}
    return c


def _progress(course: dict, enr: dict | None) -> dict:
    total = len(course.get("lessons", []))
    done = len(enr.get("completed_lessons", [])) if enr else 0
    return {"enrolled": bool(enr), "completed_lessons": enr.get("completed_lessons", []) if enr else [],
            "lessons_done": done, "lessons_total": total,
            "percent": round(100 * done / total) if total else 0,
            "best_score": enr.get("best_score") if enr else None,
            "passed": bool(enr and enr.get("passed")),
            "certificate_id": enr.get("certificate_id") if enr else None}


def _fingerprint(cert: dict) -> str:
    body = {k: cert[k] for k in ("id", "user_id", "user_name", "course_id", "course_title", "score", "issued_at")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _course(course_id: str) -> dict:
    c = await db.courses.find_one({"id": course_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Course not found")
    return c


@router.get("/courses")
async def courses(user=Depends(get_user_optional)):
    items = await db.courses.find({}, {"_id": 0}).to_list(200)
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
    if len(enr.get("completed_lessons", [])) < len(c.get("lessons", [])):
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
            reward = float(c.get("reward_lono", 0))
            if reward > 0:
                await credit(user["id"], reward, "learn_to_earn", f"Passed: {c['title']}", ref=cert["id"])
    return {"score": score, "passed": passed, "pass_mark": c["quiz"].get("pass_mark", 0.7),
            "results": results, "reward": reward, "certificate": cert,
            "certificate_id": (cert or {}).get("id") or enr.get("certificate_id")}


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
