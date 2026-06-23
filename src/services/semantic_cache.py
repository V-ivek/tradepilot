"""Semantic cache for specialist-agent responses.

Keys are derived from ``(agent_name, prompt_hash, sorted_tickers, language)``.
Bypass keywords in the user prompt (``refresh``, ``latest``, ``current``)
skip the cache — users who explicitly ask for fresh data should get a live
call. Per-agent TTLs come from Settings.
"""

import hashlib
from typing import Any

from src.config.settings import Settings, get_settings
from src.services.cache import CacheBackend, HashCacheBackend

BYPASS_KEYWORDS = {"refresh", "latest", "current"}

_AGENT_TTL_ATTR = {
    "finance": "semantic_cache_finance_ttl",
    "stock": "semantic_cache_stock_ttl",
    "fundamentals": "semantic_cache_fundamentals_ttl",
    "estimates": "semantic_cache_estimates_ttl",
}


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.strip().lower().encode("utf-8")).hexdigest()[:16]


def should_bypass(prompt: str) -> bool:
    tokens = {t.strip(".,!?").lower() for t in prompt.split()}
    return bool(tokens & BYPASS_KEYWORDS)


def build_key(
    *,
    agent_name: str,
    prompt: str,
    active_tickers: list[str] | None = None,
    language: str = "en",
) -> str:
    tickers = sorted({t.upper() for t in (active_tickers or [])})
    return f"{agent_name}:{_prompt_hash(prompt)}:{','.join(tickers)}:{language}"


class SemanticCache:
    """Wraps a :class:`CacheBackend` with agent-aware keying and TTL."""

    def __init__(
        self,
        backend: CacheBackend | None = None,
        settings: Settings | None = None,
    ):
        self._backend = backend or HashCacheBackend()
        self._settings = settings or get_settings()

    def _ttl_for(self, agent_name: str) -> int | None:
        attr = _AGENT_TTL_ATTR.get(agent_name)
        if attr is None:
            return None
        return int(getattr(self._settings, attr))

    def lookup(
        self,
        *,
        agent_name: str,
        prompt: str,
        active_tickers: list[str] | None = None,
        language: str = "en",
    ) -> Any | None:
        if not self._settings.semantic_cache_enabled:
            return None
        if should_bypass(prompt):
            return None
        key = build_key(
            agent_name=agent_name,
            prompt=prompt,
            active_tickers=active_tickers,
            language=language,
        )
        return self._backend.get(key)

    def store(
        self,
        *,
        agent_name: str,
        prompt: str,
        value: Any,
        active_tickers: list[str] | None = None,
        language: str = "en",
    ) -> None:
        if not self._settings.semantic_cache_enabled:
            return
        if should_bypass(prompt):
            return
        key = build_key(
            agent_name=agent_name,
            prompt=prompt,
            active_tickers=active_tickers,
            language=language,
        )
        self._backend.set(key, value, ttl=self._ttl_for(agent_name))
