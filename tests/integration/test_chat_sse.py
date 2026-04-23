import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.agent.graph import build_graph
from src.api.middleware.rate_limit import reset_limiter
from src.api.routes import chat
from src.config.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "30")
    get_settings.cache_clear()
    reset_limiter()
    yield
    get_settings.cache_clear()
    reset_limiter()


def _token(sub: str = "u1") -> str:
    return jwt.encode({"sub": sub}, "test-secret", algorithm="HS256")


def _app_with_graph(**node_overrides):
    """Build a minimal FastAPI app whose /chat uses an overridable graph."""
    graph = build_graph(nodes=node_overrides) if node_overrides else build_graph()
    app = FastAPI()
    app.state.graph = graph
    app.include_router(chat.router)
    return app


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Split raw SSE text into (event, data) tuples."""
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
        elif line == "":
            if current_event is not None and data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    payload = {"raw": "\n".join(data_lines)}
                events.append((current_event, payload))
            current_event = None
            data_lines = []
    return events


async def _quote_guard(state, *, model=None):
    state["next_node"] = "stock_agent"
    state["category"] = "stock"
    state.setdefault("blocks", [])
    state.setdefault("active_tickers", ["AAPL"])
    return state


async def _quote_stock(state, *, model=None):
    state.setdefault("blocks", []).append(
        {
            "type": "quote",
            "symbol": "AAPL",
            "price": "189.55",
            "change": "1.23",
            "change_pct": "0.65",
        }
    )
    return state


def test_chat_requires_auth():
    app = _app_with_graph(guard=_quote_guard, stock_agent=_quote_stock)
    client = TestClient(app)
    r = client.post("/chat", json={"user_input": "AAPL?"})
    assert r.status_code == 401


def test_chat_streams_quote_block_and_message_end():
    app = _app_with_graph(guard=_quote_guard, stock_agent=_quote_stock)
    client = TestClient(app)
    r = client.post(
        "/chat",
        json={"user_input": "AAPL?"},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert r.status_code == 200

    events = _parse_sse(r.text)
    event_names = [e for e, _ in events]
    assert event_names[0] == "message_start"
    assert "block" in event_names
    assert event_names[-1] == "message_end"

    block_events = [payload for name, payload in events if name == "block"]
    assert any(b.get("type") == "quote" for b in block_events)


def test_chat_creates_new_conversation_when_none_provided():
    app = _app_with_graph(guard=_quote_guard, stock_agent=_quote_stock)
    client = TestClient(app)
    r = client.post(
        "/chat",
        json={"user_input": "AAPL?"},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    events = _parse_sse(r.text)
    start = next(p for n, p in events if n == "message_start")
    assert "conversation_id" in start
    assert start["conversation_id"]


def test_chat_uses_existing_conversation_when_id_provided():
    app = _app_with_graph(guard=_quote_guard, stock_agent=_quote_stock)
    client = TestClient(app)
    token = _token()

    first = client.post(
        "/chat",
        json={"user_input": "AAPL?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    conv_id = next(p for n, p in _parse_sse(first.text) if n == "message_start")["conversation_id"]

    second = client.post(
        "/chat",
        json={"user_input": "again", "conversation_id": conv_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    events = _parse_sse(second.text)
    start = next(p for n, p in events if n == "message_start")
    assert start["conversation_id"] == conv_id


def test_chat_rejects_overlong_input():
    app = _app_with_graph(guard=_quote_guard, stock_agent=_quote_stock)
    client = TestClient(app)
    r = client.post(
        "/chat",
        json={"user_input": "x" * 2001},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert r.status_code == 422


def test_chat_forbids_cross_user_conversation_access():
    app = _app_with_graph(guard=_quote_guard, stock_agent=_quote_stock)
    client = TestClient(app)

    alice = client.post(
        "/chat",
        json={"user_input": "hi"},
        headers={"Authorization": f"Bearer {_token('alice')}"},
    )
    conv_id = next(p for n, p in _parse_sse(alice.text) if n == "message_start")["conversation_id"]

    bob = client.post(
        "/chat",
        json={"user_input": "steal", "conversation_id": conv_id},
        headers={"Authorization": f"Bearer {_token('bob')}"},
    )
    assert bob.status_code == 403
