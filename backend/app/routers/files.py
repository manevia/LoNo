import asyncio
import re

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from .. import config
from ..db import db
from ..security import get_user
from ..storage import storage
from ..util import now_iso, uid

router = APIRouter(tags=["files"])
ALLOWED = ("video/", "audio/", "image/")


@router.post("/storage/upload")
async def upload(file: UploadFile = File(...), user=Depends(get_user)):
    ct = file.content_type or "application/octet-stream"
    if not ct.startswith(ALLOWED):
        raise HTTPException(400, "Upload a video, audio or image file")
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    name = file.filename or "upload"
    ext = re.sub(r"[^a-z0-9]", "", name.rsplit(".", 1)[-1].lower())[:5] if "." in name else "bin"
    fid = uid()
    key = f"uploads/{user['id']}/{fid}.{ext or 'bin'}"
    # Stream to a temporary file (1 MB at a time) so a long match recording never sits in memory.
    tmp = storage.temp_dir() / f"{fid}.part"
    size = 0
    try:
        with open(tmp, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File is over the {config.MAX_UPLOAD_MB} MB limit")
                await asyncio.to_thread(out.write, chunk)
        await storage.put_file(key, tmp, ct)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    await db.files.insert_one({"id": fid, "user_id": user["id"], "storage_path": key, "original_filename": name,
                               "content_type": ct, "size": size, "is_deleted": False, "created_at": now_iso()})
    return {"file_id": fid, "path": key, "url": f"/api/files/{key}", "content_type": ct, "size": size}


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=100)
    size: int = Field(gt=0)


@router.get("/storage/mode")
async def storage_mode():
    """Whether the browser should upload straight to object storage (Cloudflare R2 / S3)."""
    return {"direct": bool(getattr(storage, "direct_uploads", False)), "max_mb": config.MAX_UPLOAD_MB}


@router.post("/storage/upload-url")
async def upload_url(body: UploadRequest, user=Depends(get_user)):
    """Step 1 of a direct upload: a signed URL to PUT the file to. The file is recorded
    as pending until step 2 confirms it arrived."""
    if not getattr(storage, "direct_uploads", False):
        raise HTTPException(409, "Direct uploads aren't used with this storage; POST /api/storage/upload instead")
    ct = body.content_type
    if not ct.startswith(("video/", "audio/", "image/")):
        raise HTTPException(400, "Upload a video, audio or image file")
    if body.size > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is over the {config.MAX_UPLOAD_MB} MB limit")
    name = body.filename
    ext = re.sub(r"[^a-z0-9]", "", name.rsplit(".", 1)[-1].lower())[:5] if "." in name else "bin"
    fid = uid()
    key = f"uploads/{user['id']}/{fid}.{ext or 'bin'}"
    await db.files.insert_one({"id": fid, "user_id": user["id"], "storage_path": key, "original_filename": name,
                               "content_type": ct, "size": body.size, "is_deleted": False, "pending": True,
                               "created_at": now_iso()})
    return {"file_id": fid, "put_url": await storage.presign_put(key, ct), "headers": {"Content-Type": ct}, "path": key}


class CompleteIn(BaseModel):
    file_id: str


@router.post("/storage/complete")
async def upload_complete(body: CompleteIn, user=Depends(get_user)):
    """Step 2: confirm the object arrived with the declared size, then make it usable."""
    rec = await db.files.find_one({"id": body.file_id, "user_id": user["id"]})
    if not rec:
        raise HTTPException(404, "Upload not found")
    if not rec.get("pending"):
        return {"file_id": rec["id"], "path": rec["storage_path"], "url": f"/api/files/{rec['storage_path']}",
                "content_type": rec["content_type"], "size": rec["size"]}
    actual = await storage.size(rec["storage_path"])
    if actual is None:
        raise HTTPException(409, "The file hasn't arrived in storage yet")
    if actual > config.MAX_UPLOAD_MB * 1024 * 1024 or actual != rec["size"]:
        await storage.delete(rec["storage_path"])
        await db.files.update_one({"id": rec["id"]}, {"$set": {"is_deleted": True}})
        raise HTTPException(422, "The uploaded file doesn't match what was announced")
    await db.files.update_one({"id": rec["id"]}, {"$set": {"pending": False}})
    return {"file_id": rec["id"], "path": rec["storage_path"], "url": f"/api/files/{rec['storage_path']}",
            "content_type": rec["content_type"], "size": actual}


@router.get("/files/{path:path}")
async def download(path: str, request: Request, exp: int | None = None, sig: str | None = None):
    rec = await db.files.find_one({"storage_path": path, "is_deleted": False, "pending": {"$ne": True}})
    if not rec:
        raise HTTPException(404, "File not found")
    if rec.get("protected"):
        raise HTTPException(403, "This media is only available with a pass, from My passes.")
    if path.startswith("recordings/"):
        # Broadcast recordings stay private until the creator publishes them:
        # unpublished ones need a short-lived signed link issued to the owner.
        from ..broadcast.secrets_box import verify
        import time
        recording = await db.recordings.find_one({"url": f"/api/files/{path}"}, {"visibility": 1})
        if not recording or recording.get("visibility") != "public":
            if not (exp and sig and exp > time.time() and verify(path, sig, str(exp))):
                raise HTTPException(403, "This recording is private")
            return await storage.serve(path, rec.get("content_type", "application/octet-stream"), request, ttl=300)
    return await storage.serve(path, rec.get("content_type", "application/octet-stream"), request)
