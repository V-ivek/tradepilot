import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.api.middleware.rate_limit import (
    RateLimiter,
    rate_limit_dependency,
    reset_limiter,
)
from src.config.settings import get_settings


def test_limiter_allows_up_to_limit():
    rl = RateLimiter(limit=3, window_seconds=60)
    now = 0.0
    for i in range(3):
        allowed, remaining, _ = rl.hit("u", now=now)
        assert allowed is True
        assert remaining == 2 - i


def test_limiter_blocks_beyond_limit():
    rl = RateLimiter(limit=2, window_seconds=60)
    rl.hit("u", now=0)
    rl.hit("u", now=1)
    allowed, remaining, retry_after = rl.hit("u", now=2)
    assert allowed is False
    assert remaining == 0
    assert retry_after >= 1


def test_limiter_isolates_users():
    rl = RateLimiter(limit=1)
    rl.hit("a")
    allowed, _, _ = rl.hit("b")
    assert allowed is True


def test_limiter_recovers_after_window():
    rl = RateLimiter(limit=1, window_seconds=10)
    assert rl.hit("u", now=0)[0] is True
    assert rl.hit("u", now=5)[0] is False
    assert rl.hit("u", now=11)[0] is True


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    reset_limiter()
    yield
    get_settings.cache_clear()
    reset_limiter()


def _token(sub: str = "u1") -> str:
    return jwt.encode({"sub": sub}, "test-secret", algorithm="HS256")


def test_route_returns_429_when_limit_exceeded():
    app = FastAPI()

    @app.get("/ping")
    async def ping(user=Depends(rate_limit_dependency)):
        return {"user": user["user_id"]}

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_token()}"}

    assert client.get("/ping", headers=headers).status_code == 200
    assert client.get("/ping", headers=headers).status_code == 200
    r = client.get("/ping", headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_route_per_user_isolation():
    app = FastAPI()

    @app.get("/ping")
    async def ping(user=Depends(rate_limit_dependency)):
        return {"user": user["user_id"]}

    client = TestClient(app)
    hdr_a = {"Authorization": f"Bearer {_token('a')}"}
    hdr_b = {"Authorization": f"Bearer {_token('b')}"}

    assert client.get("/ping", headers=hdr_a).status_code == 200
    assert client.get("/ping", headers=hdr_a).status_code == 200
    assert client.get("/ping", headers=hdr_a).status_code == 429
    # user b is unaffected
    assert client.get("/ping", headers=hdr_b).status_code == 200


def test_limiter_requires_auth():
    app = FastAPI()

    @app.get("/ping")
    async def ping(user=Depends(rate_limit_dependency)):
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/ping")
    assert r.status_code == 401
