"""Cache backend Protocol + in-memory hash implementation."""

import time
from typing import Any, Protocol


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...
    def delete(self, key: str) -> None: ...


class HashCacheBackend:
    """Dict-backed cache with per-entry TTL using ``time.monotonic``."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}

    def _now(self) -> float:
        return time.monotonic()

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at <= self._now():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = self._now() + ttl if ttl else None
        self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
