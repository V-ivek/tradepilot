import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.api.routes import conversations
from src.config.settings import get_settings
from src.services.conversation import ConversationService


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _token(sub: str) -> str:
    return jwt.encode({"sub": sub}, "test-secret", algorithm="HS256")


@pytest.fixture
def app_and_svc():
    svc = ConversationService()
    app = FastAPI()
    app.state.conversation_service = svc
    app.include_router(conversations.router)
    return app, svc


def test_list_returns_only_callers_conversations(app_and_svc):
    app, svc = app_and_svc
    svc.create_conversation("alice")
    svc.create_conversation("alice")
    svc.create_conversation("bob")

    client = TestClient(app)
    r = client.get("/conversations", headers={"Authorization": f"Bearer {_token('alice')}"})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_requires_auth(app_and_svc):
    app, _ = app_and_svc
    client = TestClient(app)
    assert client.get("/conversations").status_code == 401


def test_get_conversation_returns_details(app_and_svc):
    app, svc = app_and_svc
    conv = svc.create_conversation("alice")
    client = TestClient(app)

    r = client.get(
        f"/conversations/{conv.id}",
        headers={"Authorization": f"Bearer {_token('alice')}"},
    )
    assert r.status_code == 200
    assert r.json()["id"] == conv.id


def test_get_conversation_404(app_and_svc):
    app, _ = app_and_svc
    client = TestClient(app)
    r = client.get(
        "/conversations/nope",
        headers={"Authorization": f"Bearer {_token('alice')}"},
    )
    assert r.status_code == 404


def test_get_conversation_403_for_other_user(app_and_svc):
    app, svc = app_and_svc
    conv = svc.create_conversation("alice")
    client = TestClient(app)

    r = client.get(
        f"/conversations/{conv.id}",
        headers={"Authorization": f"Bearer {_token('bob')}"},
    )
    assert r.status_code == 403


def test_delete_removes_conversation(app_and_svc):
    app, svc = app_and_svc
    conv = svc.create_conversation("alice")
    client = TestClient(app)

    r = client.delete(
        f"/conversations/{conv.id}",
        headers={"Authorization": f"Bearer {_token('alice')}"},
    )
    assert r.status_code == 204
    assert svc.get_conversation(conv.id) is None


def test_delete_403_for_other_user(app_and_svc):
    app, svc = app_and_svc
    conv = svc.create_conversation("alice")
    client = TestClient(app)

    r = client.delete(
        f"/conversations/{conv.id}",
        headers={"Authorization": f"Bearer {_token('bob')}"},
    )
    assert r.status_code == 403
    assert svc.get_conversation(conv.id) is not None
