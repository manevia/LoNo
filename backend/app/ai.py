"""Claude (Anthropic API) and speech-to-text helpers."""
import io

import httpx
from fastapi import HTTPException

from . import config

_client = None


def claude():
    global _client
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(503, "AI features are off. Set ANTHROPIC_API_KEY on the server to turn them on.")
    if _client is None:
        from anthropic import AsyncAnthropic
        _client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


async def complete(system: str, messages: list[dict], max_tokens: int = 800) -> str:
    try:
        resp = await claude().messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=max_tokens, system=system, messages=messages)
    except HTTPException:
        raise
    except Exception as e:  # anthropic.APIError and network errors
        raise HTTPException(502, f"AI request failed: {e}")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


async def transcribe(data: bytes, content_type: str) -> dict:
    """Returns OpenAI verbose_json: {text, language, segments:[{start,end,text}]}."""
    if not config.TRANSCRIBE_API_KEY:
        raise HTTPException(503, "Captions are off. Set TRANSCRIBE_API_KEY (or OPENAI_API_KEY) on the server.")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Media is over the 25 MB transcription limit. Upload a shorter clip.")
    ext = "mp4" if "video" in content_type else "mp3" if "mpeg" in content_type or "mp3" in content_type else "wav"
    files = {"file": (f"media.{ext}", io.BytesIO(data), content_type or "application/octet-stream")}
    form = {"model": config.TRANSCRIBE_MODEL, "response_format": "verbose_json",
            "timestamp_granularities[]": "segment"}
    try:
        async with httpx.AsyncClient(timeout=300) as hc:
            r = await hc.post(f"{config.TRANSCRIBE_BASE_URL}/audio/transcriptions",
                              headers={"Authorization": f"Bearer {config.TRANSCRIBE_API_KEY}"},
                              data=form, files=files)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Transcription failed ({e.response.status_code}): {e.response.text[:200]}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Transcription failed: {e}")


def _ts(t: float) -> str:
    h, m, s = int(t // 3600), int((t % 3600) // 60), t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def to_vtt(result: dict) -> str:
    lines = ["WEBVTT", ""]
    segs = result.get("segments") or []
    if not segs:
        return "\n".join(lines + ["00:00:00.000 --> 00:05:00.000", (result.get("text") or "").strip(), ""])
    for s in segs:
        if s.get("start") is None or s.get("end") is None:
            continue
        lines += [f"{_ts(s['start'])} --> {_ts(s['end'])}", (s.get("text") or "").strip(), ""]
    return "\n".join(lines)
