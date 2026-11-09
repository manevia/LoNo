"""Relay manager: one ffmpeg process per (session, target). Targets are simulcast
destinations and the recorder. Each process is independent, so a failing
destination never stops the others; a targeted retry restarts just that one.

Status per target: idle → connecting → live → (failed | stopped | waiting)."""
import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

from .. import config
from .secrets_box import redact

log = logging.getLogger("lono.broadcast")


@dataclass
class Relay:
    session_id: str
    target_id: str
    args: list[str]
    secrets: tuple[str, ...] = ()
    state: str = "idle"
    error: str | None = None
    attempts: int = 0
    started_at: float | None = None
    live_at: float | None = None
    out_seconds: float = 0.0
    proc: asyncio.subprocess.Process | None = None
    task: asyncio.Task | None = None
    stderr_tail: list[str] = field(default_factory=list)

    def view(self) -> dict:
        return {"state": self.state, "error": self.error, "attempts": self.attempts,
                "live_since": self.live_at, "sent_seconds": round(self.out_seconds, 1)}


ERROR_HINTS = [
    (r"Connection refused|Connection timed out|Network is unreachable|No route to host|Name or service not known|Cannot assign",
     "Couldn't reach the destination server. Check the server URL."),
    (r"401|403|Unauthorized|Forbidden|unauthori[sz]ed|Server error: Authentication|NetStream.Publish.BadName|BadName",
     "The destination rejected the stream key. Copy a fresh key from the platform."),
    (r"Input/output error|End of file|Broken pipe|Connection reset",
     "The destination closed the connection."),
    (r"Server returned 404|404 Not Found|Error opening input|does not contain any stream",
     "No live feed from your encoder yet."),
    (r"Protocol not found|Unknown protocol",
     "This destination's protocol isn't supported by the server's ffmpeg build."),
]


def explain(stderr: str) -> str:
    for pattern, message in ERROR_HINTS:
        if re.search(pattern, stderr, re.I):
            return message
    return "The stream to this destination stopped."


class RelayManager:
    def __init__(self):
        self.relays: dict[tuple[str, str], Relay] = {}
        self.on_change = None   # async fn(session_id, target_id, state, error)

    async def _notify(self, r: Relay):
        if self.on_change:
            try:
                await self.on_change(r.session_id, r.target_id, r.state, r.error)
            except Exception:
                log.exception("relay listener failed")

    def get(self, session_id: str) -> dict[str, dict]:
        return {t: r.view() for (s, t), r in self.relays.items() if s == session_id}

    async def start(self, session_id: str, target_id: str, args: list[str], secrets: tuple[str, ...] = ()):
        key = (session_id, target_id)
        old = self.relays.get(key)
        if old and old.state in ("connecting", "live"):
            return old  # already running: starting twice is safe
        if old:
            await self._kill(old)
        r = Relay(session_id, target_id, args, secrets, attempts=(old.attempts if old else 0))
        self.relays[key] = r
        r.task = asyncio.create_task(self._run(r))
        return r

    async def _run(self, r: Relay):
        r.attempts += 1
        r.state, r.error, r.started_at, r.live_at, r.out_seconds = "connecting", None, time.time(), None, 0.0
        try:
            r.proc = await asyncio.create_subprocess_exec(
                config.FFMPEG_BIN, *r.args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except FileNotFoundError:
            r.state, r.error = "failed", "ffmpeg isn't installed on the server."
            return
        err_task = asyncio.create_task(self._read_err(r))
        async for raw in r.proc.stdout:  # -progress pipe:1 → key=value lines
            line = raw.decode(errors="ignore").strip()
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                try:
                    us = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                r.out_seconds = us / 1_000_000
                if r.out_seconds > 0.5 and r.state == "connecting":
                    r.state, r.live_at = "live", time.time()
                    await self._notify(r)
        code = await r.proc.wait()
        await err_task
        if r.state == "stopped":
            return
        tail = redact("\n".join(r.stderr_tail[-20:]), *r.secrets)
        r.state = "failed"
        r.error = explain(tail) if code != 0 or r.live_at is None else "The stream to this destination ended."
        log.warning("relay %s/%s exited (%s): %s", r.session_id, r.target_id, code, r.error)
        await self._notify(r)

    async def _read_err(self, r: Relay):
        async for raw in r.proc.stderr:
            r.stderr_tail.append(raw.decode(errors="ignore").strip())
            del r.stderr_tail[:-50]

    async def _kill(self, r: Relay):
        r.state = "stopped"
        if r.proc and r.proc.returncode is None:
            try:
                r.proc.terminate()
                await asyncio.wait_for(r.proc.wait(), 5)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    r.proc.kill()
                except ProcessLookupError:
                    pass
        if r.task:
            try:
                await asyncio.wait_for(r.task, 5)
            except (asyncio.TimeoutError, Exception):
                pass

    async def stop(self, session_id: str, target_id: str | None = None):
        for (s, t), r in list(self.relays.items()):
            if s == session_id and (target_id is None or t == target_id):
                await self._kill(r)

    async def stop_all(self):
        for r in list(self.relays.values()):
            await self._kill(r)


manager = RelayManager()
