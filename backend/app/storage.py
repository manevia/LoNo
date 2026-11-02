"""Pluggable object storage: local disk (default) or any S3-compatible bucket."""
import asyncio
import os
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse

from . import config

CHUNK = 1024 * 1024


class LocalStorage:
    name = "local"

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise HTTPException(400, "Invalid path")
        return p

    async def put(self, key: str, data: bytes, content_type: str):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_bytes, data)

    async def read(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise HTTPException(404, "File not found in storage")
        return await asyncio.to_thread(p.read_bytes)

    async def serve(self, key: str, content_type: str, request: Request) -> Response:
        """Stream with HTTP Range support so video seeking works."""
        p = self._path(key)
        if not p.exists():
            raise HTTPException(404, "File not found in storage")
        size = p.stat().st_size
        start, end = 0, size - 1
        rng = request.headers.get("range")
        status = 200
        if rng and rng.startswith("bytes="):
            s, _, e = rng[6:].split(",")[0].partition("-")
            try:
                if s:
                    start = int(s)
                    end = int(e) if e else size - 1
                else:  # suffix range: last N bytes
                    start = max(0, size - int(e))
            except ValueError:
                raise HTTPException(416, "Bad range")
            end = min(end, size - 1)
            if start > end:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
            status = 206

        def body():
            with open(p, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        break
                    left -= len(chunk)
                    yield chunk

        headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1),
                   "Cache-Control": "public, max-age=3600"}
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return StreamingResponse(body(), status_code=status, media_type=content_type, headers=headers)


class S3Storage:
    name = "s3"

    def __init__(self):
        import boto3
        self.bucket = config.S3_BUCKET
        self.s3 = boto3.client("s3", region_name=config.S3_REGION, endpoint_url=config.S3_ENDPOINT_URL)

    async def put(self, key: str, data: bytes, content_type: str):
        await asyncio.to_thread(self.s3.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    async def read(self, key: str) -> bytes:
        obj = await asyncio.to_thread(self.s3.get_object, Bucket=self.bucket, Key=key)
        return await asyncio.to_thread(obj["Body"].read)

    async def serve(self, key: str, content_type: str, request: Request) -> Response:
        url = await asyncio.to_thread(
            self.s3.generate_presigned_url, "get_object",
            Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=3600)
        return RedirectResponse(url, status_code=307)


def _make():
    if config.STORAGE_BACKEND == "s3":
        if not config.S3_BUCKET:
            raise RuntimeError("STORAGE_BACKEND=s3 requires S3_BUCKET")
        return S3Storage()
    return LocalStorage(config.LOCAL_STORAGE_DIR)


storage = _make()
