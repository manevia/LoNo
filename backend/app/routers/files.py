import asyncio
import re

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


@router.get("/files/{path:path}")
async def download(path: str, request: Request, exp: int | None = None, sig: str | None = None):
    rec = await db.files.find_one({"storage_path": path, "is_deleted": False})
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
    return await storage.serve(path, rec.get("content_type", "application/octet-stream"), request)
