"""MediaMTX link: path status from its control API, and a monitor loop that
turns readiness changes into broadcast events (encoder connected / dropped)."""
import asyncio
import logging
import time

import httpx

from .. import config

log = logging.getLogger("lono.broadcast")
_samples: dict[str, tuple[float, int]] = {}   # path -> (time, bytesReceived) for bitrate
listeners = []                                 # async fn(path, ready: bool)


async def path_info(path: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=3) as hc:
            r = await hc.get(f"{config.MEDIA_API_URL}/v3/paths/get/{path}")
        if r.status_code != 200:
            return None
        d = r.json()
    except httpx.HTTPError:
        return None
    now, received = time.time(), d.get("bytesReceived", 0)
    prev = _samples.get(path)
    _samples[path] = (now, received)
    kbps = None
    if prev and now > prev[0] and received >= prev[1]:
        kbps = round((received - prev[1]) * 8 / 1000 / (now - prev[0]))
    tracks = d.get("tracks") or []
    return {"ready": bool(d.get("ready")), "since": d.get("readyTime"), "tracks": tracks,
            "has_video": any(t.lower() in ("h264", "h265", "av1", "vp9", "vp8", "mpeg-4 video", "mjpeg") for t in tracks),
            "has_audio": any(t.lower() in ("mpeg-4 audio", "opus", "aac", "mpeg-1/2 audio", "g711", "lpcm", "ac-3") for t in tracks),
            "source": (d.get("source") or {}).get("type"), "readers": len(d.get("readers") or []),
            "bytes_received": received, "bitrate_kbps": kbps}


async def list_ready() -> set[str]:
    try:
        async with httpx.AsyncClient(timeout=3) as hc:
            r = await hc.get(f"{config.MEDIA_API_URL}/v3/paths/list", params={"itemsPerPage": 1000})
        return {p["name"] for p in r.json().get("items", []) if p.get("ready")}
    except (httpx.HTTPError, ValueError):
        return set()


async def monitor(stop: asyncio.Event):
    """Poll every 2 s; notify listeners when a live/* path becomes ready or not."""
    known: set[str] = set()
    while not stop.is_set():
        ready = {p for p in await list_ready() if p.startswith("live/")}
        for path in ready - known:
            for fn in listeners:
                await _safe(fn, path, True)
        for path in known - ready:
            for fn in listeners:
                await _safe(fn, path, False)
        known = ready
        try:
            await asyncio.wait_for(stop.wait(), 2)
        except asyncio.TimeoutError:
            pass


async def _safe(fn, *a):
    try:
        await fn(*a)
    except Exception:  # never let one listener stop monitoring
        log.exception("broadcast listener failed")
