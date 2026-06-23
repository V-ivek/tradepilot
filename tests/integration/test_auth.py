import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.api.middleware.auth import get_current_user
from src.config.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    app = FastAPI()

    @app.get("/me")
    async def me(user=pytest.importorskip("fastapi").Depends(get_current_user)):
        return user

    return TestClient(app)


def _make_token(sub: str = "u1", secret: str = "test-secret", algo: str = "HS256"):
    return jwt.encode({"sub": sub}, secret, algorithm=algo)


def test_missing_header_returns_401(client):
    r = client.get("/me")
    assert r.status_code == 401


def test_non_bearer_scheme_returns_401(client):
    r = client.get("/me", headers={"Authorization": "Basic foo"})
    assert r.status_code == 401


def test_invalid_token_returns_401(client):
    r = client.get("/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_token_missing_sub_returns_401(client):
    bad = jwt.encode({"foo": "bar"}, "test-secret", algorithm="HS256")
    r = client.get("/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_wrong_secret_returns_401(client):
    token = _make_token(secret="different-secret")
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_valid_token_returns_user_id(client):
    token = _make_token("user-123")
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "user-123"
