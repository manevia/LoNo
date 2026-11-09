"""Small in-memory sliding-window rate limiter.

Good enough for a single API process (the default deployment). If you run several
API replicas behind a load balancer, move this to Redis so limits are shared."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_sec: int, message: str):
        self.limit, self.window, self.message = limit, window_sec, message
        self.hits: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str, now: float):
        q = self.hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if not q:
            self.hits.pop(key, None)
        return self.hits.get(key, deque())

    def check(self, key: str):
        """Raise 429 if `key` has used up its allowance (does not record a hit)."""
        now = time.monotonic()
        q = self._prune(key, now)
        if len(q) >= self.limit:
            retry = int(q[0] + self.window - now) + 1
            minutes = max(1, round(retry / 60))
            raise HTTPException(429, f"{self.message} Try again in about {minutes} minute{'s' if minutes != 1 else ''}.",
                                headers={"Retry-After": str(retry)})

    def hit(self, key: str):
        self.hits[key].append(time.monotonic())

    def reset(self, key: str):
        self.hits.pop(key, None)

    def clear(self):
        self.hits.clear()


def client_ip(request: Request) -> str:
    # Behind nginx (Docker mode) uvicorn's --proxy-headers sets request.client from X-Forwarded-For.
    return request.client.host if request.client else "unknown"
