import time

import pytest

from src.config.settings import get_settings
from src.services.cache import HashCacheBackend
from src.services.semantic_cache import SemanticCache, build_key, should_bypass


def _set_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_build_key_is_stable_across_case_and_ticker_order():
    k1 = build_key(agent_name="stock", prompt="AAPL price?", active_tickers=["AAPL", "TSLA"])
    k2 = build_key(agent_name="stock", prompt="  aapl PRICE? ", active_tickers=["tsla", "AAPL"])
    assert k1 == k2


def test_build_key_differs_by_agent():
    a = build_key(agent_name="stock", prompt="price", active_tickers=["AAPL"])
    b = build_key(agent_name="finance", prompt="price", active_tickers=["AAPL"])
    assert a != b


def test_should_bypass_detects_keywords():
    assert should_bypass("please refresh the price")
    assert should_bypass("what's the latest quote?")
    assert should_bypass("current price of AAPL")
    assert not should_bypass("price of AAPL")


def test_store_and_lookup_hit(monkeypatch):
    _set_env(monkeypatch)
    cache = SemanticCache(backend=HashCacheBackend())

    cache.store(
        agent_name="stock",
        prompt="price of AAPL",
        value={"data": "cached"},
        active_tickers=["AAPL"],
    )
    hit = cache.lookup(agent_name="stock", prompt="price of AAPL", active_tickers=["AAPL"])

    assert hit == {"data": "cached"}


def test_bypass_keyword_skips_lookup(monkeypatch):
    _set_env(monkeypatch)
    cache = SemanticCache(backend=HashCacheBackend())

    cache.store(agent_name="stock", prompt="price of AAPL", value={"x": 1})
    miss = cache.lookup(agent_name="stock", prompt="refresh price of AAPL")

    assert miss is None


def test_bypass_keyword_skips_store(monkeypatch):
    _set_env(monkeypatch)
    backend = HashCacheBackend()
    cache = SemanticCache(backend=backend)

    cache.store(agent_name="stock", prompt="refresh price of AAPL", value={"x": 1})

    assert cache.lookup(agent_name="stock", prompt="price of AAPL") is None


def test_cache_disabled_by_settings(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "false")
    get_settings.cache_clear()
    cache = SemanticCache(backend=HashCacheBackend())

    cache.store(agent_name="stock", prompt="AAPL price", value={"x": 1})

    assert cache.lookup(agent_name="stock", prompt="AAPL price") is None


def test_per_agent_ttls_applied(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.setenv("SEMANTIC_CACHE_STOCK_TTL", "1")
    monkeypatch.setenv("SEMANTIC_CACHE_FINANCE_TTL", "3600")
    get_settings.cache_clear()

    cache = SemanticCache(backend=HashCacheBackend())

    cache.store(agent_name="stock", prompt="AAPL", value="stock")
    cache.store(agent_name="finance", prompt="AAPL", value="finance")

    assert cache.lookup(agent_name="stock", prompt="AAPL") == "stock"
    time.sleep(1.05)
    # stock expired, finance still cached
    assert cache.lookup(agent_name="stock", prompt="AAPL") is None
    assert cache.lookup(agent_name="finance", prompt="AAPL") == "finance"


def test_unknown_agent_has_no_ttl(monkeypatch):
    _set_env(monkeypatch)
    cache = SemanticCache(backend=HashCacheBackend())

    cache.store(agent_name="news", prompt="AAPL", value=1)

    assert cache.lookup(agent_name="news", prompt="AAPL") == 1
