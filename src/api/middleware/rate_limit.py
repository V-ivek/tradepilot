"""Per-user sliding-window rate limiter.

In-memory. One bucket per ``user_id``. Each call to :func:`check_rate_limit`
drops timestamps older than the window and raises ``HTTPException(429)`` if
the remaining count exceeds ``settings.rate_limit_per_minute``.

Production will swap in a Redis-backed implementation; the API is the seam.
"""

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import Depends, HTTPException, status

from src.api.middleware.auth import get_current_user
from src.config.settings import get_settings

WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(self, *, limit: int, window_seconds: int = WINDOW_SECONDS):
        self._limit = limit
        self._window = window_seconds
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def hit(self, user_id: str, now: float | None = None) -> tuple[bool, int, int]:
        """Record a call for ``user_id``. Returns (allowed, remaining, retry_after)."""
        now = now if now is not None else time.monotonic()
        bucket = self._buckets[user_id]
        cutoff = now - self._window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self._limit:
            retry_after = max(1, int(self._window - (now - bucket[0])))
            return False, 0, retry_after

        bucket.append(now)
        return True, self._limit - len(bucket), 0


_default_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter(limit=get_settings().rate_limit_per_minute)
    return _default_limiter


def reset_limiter() -> None:
    """Used by tests to discard accumulated state."""
    global _default_limiter
    _default_limiter = None


async def rate_limit_dependency(
    user: dict = Depends(get_current_user),
    limiter: RateLimiter = Depends(get_limiter),
) -> dict:
    allowed, remaining, retry_after = limiter.hit(user["user_id"])
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    return user
