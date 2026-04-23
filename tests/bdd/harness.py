"""E2E harness used by the BDD tests.

Wires a real ``src.main`` app to a real ``gateway.main`` app using an
in-process ASGI transport. LLM-backed graph nodes are stubbed with
deterministic fakes so the entire /chat → graph → gateway → broker path
runs without network or models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from gateway import main as gateway_main
from gateway.deps import get_paper_trading, get_registry
from gateway.models import QuoteData, SymbolMatch
from gateway.providers.base import DataProvider
from gateway.providers.registry import ProviderRegistry
from src.agent.graph import build_graph
from src.api.middleware.rate_limit import reset_limiter
from src.api.routes import chat as chat_route
from src.main import create_app as create_app_main
from src.models.order import new_nonce, sign_order
from src.services.gateway import GatewayClient, set_gateway_client
from tests.gateway.fakes.paper_trading import FakePaperTradingAdapter

JWT_SECRET = "bdd-secret"
JWT_ALGO = "HS256"


# ---------- Fake data provider used by the gateway app ----------


class _FakeDataProvider(DataProvider):
    """Deterministic quotes / symbol search / news for the E2E harness."""

    async def get_quote(self, ticker: str) -> QuoteData | None:
        prices = {"AAPL": Decimal("189.55"), "TSLA": Decimal("200.00")}
        if ticker.upper() not in prices:
            return None
        return QuoteData(
            ticker=ticker.upper(),
            price=prices[ticker.upper()],
            change=Decimal("1.00"),
            change_pct=Decimal("0.5"),
        )

    async def get_company_profile(self, ticker: str):
        return None

    async def get_fundamentals(self, ticker: str, *, statement="all", period="annual"):
        return None

    async def get_price_history(self, ticker: str, *, period="1M"):
        return []

    async def search_symbols(self, query: str, *, limit=10) -> list[SymbolMatch]:
        needle = query.strip().upper()
        known = {"AAPL": "Apple Inc", "TSLA": "Tesla, Inc."}
        if needle in known:
            return [SymbolMatch(ticker=needle, name=known[needle])]
        return []

    async def get_news(self, *, query=None, tickers=None, limit=20):
        return []

    async def get_estimates(self, ticker):
        return None

    async def get_analyst_data(self, ticker):
        return None


# ---------- Deterministic fake graph nodes ----------


async def _fake_guard(state, *, model=None):
    text = state.get("user_input", "").lower()
    state.setdefault("blocks", [])
    state.setdefault("active_tickers", [])
    # Honor awaiting_confirmation like the real guard does
    if state.get("awaiting_confirmation") and state.get("pending_trade"):
        state["next_node"] = "confirmation_classifier"
        state["category"] = "trade"
        return state

    tickers = []
    for sym in ("AAPL", "TSLA"):
        if sym.lower() in text or sym in state.get("user_input", ""):
            tickers.append(sym)
    for t in tickers:
        if t not in state["active_tickers"]:
            state["active_tickers"].append(t)

    import re

    words = set(re.findall(r"[a-z']+", text))
    if {"weather", "recipe", "recipes"} & words:
        state["next_node"] = "rejection"
        state["category"] = "off_topic"
    elif {"buy", "sell", "place"} & words:
        state["next_node"] = "trade_agent"
        state["category"] = "trade"
    elif {"account", "portfolio", "positions", "orders"} & words:
        state["next_node"] = "account_agent"
        state["category"] = "account"
    elif {"etf", "etfs", "dividend", "dividends"} & words:
        state["next_node"] = "finance_agent"
        state["category"] = "finance"
    else:
        state["next_node"] = "stock_agent"
        state["category"] = "stock"
    return state


async def _fake_stock_agent(state, *, model=None):
    blocks = state.setdefault("blocks", [])
    for ticker in state.get("active_tickers") or ["AAPL"]:
        blocks.append(
            {
                "type": "quote",
                "symbol": ticker,
                "price": "189.55" if ticker == "AAPL" else "200.00",
                "change": "1.00",
                "change_pct": "0.5",
            }
        )
    blocks.append({"type": "text", "content": "Quote retrieved."})
    return state


async def _fake_finance_agent(state, *, model=None):
    state.setdefault("blocks", []).append(
        {
            "type": "text",
            "content": (
                "An ETF is an exchange-traded fund. "
                "This is educational information, not personalized advice."
            ),
        }
    )
    return state


async def _fake_account_agent(state, *, model=None):
    blocks = state.setdefault("blocks", [])
    blocks.append(
        {
            "type": "account_summary",
            "equity": "100000",
            "cash": "50000",
            "buying_power": "50000",
            "day_trade_count": 0,
            "positions_count": 0,
            "mode": "paper",
        }
    )
    blocks.append({"type": "text", "content": "Your paper trading account is ready."})
    return state


async def _fake_trade_agent(state, *, model=None):
    """Extract buy/sell + ticker + qty with naive regex, then call real prepare_order."""
    import re

    from src.tools.trading.prepare_order import _impl as prepare_order_impl

    text = state.get("user_input", "")
    m = re.search(r"\b(buy|sell)\b\s+(\d+)\s+([A-Z]{1,5})", text, re.IGNORECASE)
    blocks = state.setdefault("blocks", [])
    if not m:
        blocks.append({"type": "text", "content": "Please specify side, quantity, and symbol."})
        return state
    side, qty, symbol = m.group(1).lower(), m.group(2), m.group(3).upper()

    from src.services.gateway import get_gateway_client

    gateway = get_gateway_client()
    draft = await prepare_order_impl(
        gateway,
        JWT_SECRET,
        symbol=symbol,
        side=side,
        qty=qty,
        type="market",
    )
    if "error" in draft:
        blocks.append({"type": "text", "content": draft["error"]})
        return state

    blocks.append(
        {
            "type": "trade_intent",
            "symbol": draft["symbol"],
            "side": draft["side"],
            "qty": draft["qty"],
            "order_type": draft["type"],
            "limit_price": draft.get("limit_price"),
            "stop_price": draft.get("stop_price"),
            "time_in_force": draft.get("time_in_force", "day"),
            "estimated_cost": draft["estimated_cost"],
            "confirmation_token": draft["confirmation_token"],
            "mode": "paper",
        }
    )
    blocks.append(
        {
            "type": "text",
            "content": (
                f"Confirm PAPER order: {side.upper()} {qty} {symbol}. "
                "Paper trading only — no real money."
            ),
        }
    )
    state["pending_trade"] = draft
    state["awaiting_confirmation"] = True
    return state


async def _fake_confirmation_classifier(state, *, model=None):
    text = (state.get("user_input", "") or "").lower().strip()
    if text in {"confirm", "yes", "do it", "go ahead", "place it", "submit"}:
        state["confirmation_verdict"] = "AFFIRM"
    elif text in {"cancel", "no", "stop", "abort", "nevermind"}:
        state["confirmation_verdict"] = "DENY"
        state["pending_trade"] = None
        state["awaiting_confirmation"] = False
        state.setdefault("blocks", []).append(
            {"type": "text", "content": "Order canceled. Paper trading only."}
        )
    elif text.startswith("change"):
        state["confirmation_verdict"] = "MODIFY"
    else:
        state["confirmation_verdict"] = "UNRELATED"
    return state


FAKE_NODES = {
    "guard": _fake_guard,
    "stock_agent": _fake_stock_agent,
    "finance_agent": _fake_finance_agent,
    "account_agent": _fake_account_agent,
    "trade_agent": _fake_trade_agent,
    "confirmation_classifier": _fake_confirmation_classifier,
}


# ---------- Harness container ----------


@dataclass
class Harness:
    app: FastAPI
    gateway_app: FastAPI
    broker: FakePaperTradingAdapter
    client: TestClient
    gateway_client: GatewayClient
    http_client: httpx.AsyncClient
    conversation_ids: dict[str, str] = field(default_factory=dict)

    def token(self, user: str = "alice") -> str:
        return jwt.encode(
            {
                "sub": user,
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            JWT_SECRET,
            algorithm=JWT_ALGO,
        )

    def send(self, user_input: str, *, user: str = "alice", reuse: bool = False) -> list[dict]:
        body: dict[str, Any] = {"user_input": user_input}
        if reuse and user in self.conversation_ids:
            body["conversation_id"] = self.conversation_ids[user]
        r = self.client.post(
            "/chat",
            json=body,
            headers={"Authorization": f"Bearer {self.token(user)}"},
        )
        assert r.status_code == 200, r.text
        events = _parse_sse(r.text)
        for name, payload in events:
            if name == "message_start":
                self.conversation_ids[user] = payload["conversation_id"]
        return [p for n, p in events if n == "block"]

    def last_events(self, user_input: str, *, user: str = "alice", reuse: bool = True):
        body: dict[str, Any] = {"user_input": user_input}
        if reuse and user in self.conversation_ids:
            body["conversation_id"] = self.conversation_ids[user]
        r = self.client.post(
            "/chat",
            json=body,
            headers={"Authorization": f"Bearer {self.token(user)}"},
        )
        return r, _parse_sse(r.text)


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current = None
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("event:"):
            current = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
        elif line == "":
            if current and data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    payload = {"raw": "\n".join(data_lines)}
                events.append((current, payload))
            current = None
            data_lines = []
    return events


# ---------- Factory ----------


def build_harness(monkeypatch) -> Harness:
    # 1. Environment the app needs
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    monkeypatch.setenv("ALPACA_API_KEY_ID", "")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "100")

    from gateway.config import get_settings as gw_settings
    from src.config.settings import get_settings as app_settings

    gw_settings.cache_clear()
    app_settings.cache_clear()
    reset_limiter()

    # 2. Real gateway app with FakePaperTradingAdapter + FakeDataProvider wired in.
    gateway_app = gateway_main.create_app()
    broker = FakePaperTradingAdapter(starting_cash=Decimal("100000"), fill_price=Decimal("189.55"))
    gateway_app.state.paper_trading = broker  # satisfies get_paper_trading
    registry = ProviderRegistry([_FakeDataProvider()])

    def _registry_override():
        return registry

    def _paper_override():
        return broker

    gateway_app.dependency_overrides[get_registry] = _registry_override
    gateway_app.dependency_overrides[get_paper_trading] = _paper_override

    # 3. In-process HTTP transport from src.GatewayClient → gateway ASGI app.
    transport = httpx.ASGITransport(app=gateway_app)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://gateway")
    gateway_client = GatewayClient(base_url="http://gateway", client=http_client)
    set_gateway_client(gateway_client)

    # 4. Real app, but with fake graph nodes for deterministic LLM paths.
    app = create_app_main()
    app.state.graph = build_graph(nodes=FAKE_NODES)

    # Override the chat route's graph accessor so our stubbed graph wins even if
    # app.state.graph was replaced during lifespan.
    app.dependency_overrides[chat_route.get_graph] = lambda: app.state.graph

    client = TestClient(app)
    # Enter the context so lifespan runs; keep it open for the test.
    client.__enter__()
    app.state.graph = build_graph(nodes=FAKE_NODES)

    return Harness(
        app=app,
        gateway_app=gateway_app,
        broker=broker,
        client=client,
        gateway_client=gateway_client,
        http_client=http_client,
    )


def teardown_harness(harness: Harness) -> None:
    harness.client.__exit__(None, None, None)
    # AsyncClient.aclose is async — close via anyio
    import anyio

    anyio.from_thread.run(harness.http_client.aclose) if False else None
    # In a sync test, schedule via asyncio:
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(harness.http_client.aclose())
        loop.close()
    except Exception:
        pass
    set_gateway_client(None)


# ---------- Helpers for BDD steps ----------


def make_signed_draft(*, symbol: str = "TSLA", qty: str = "10", minutes_old: int = 0) -> dict:
    created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_old)
    data = {
        "symbol": symbol,
        "side": "buy",
        "qty": qty,
        "type": "market",
        "limit_price": None,
        "stop_price": None,
        "time_in_force": "day",
        "estimated_cost": str(Decimal(qty) * Decimal("200")),
        "nonce": new_nonce(),
        "created_at": created_at.isoformat(),
        "mode": "paper",
    }
    signable = {
        **data,
        "qty": Decimal(qty),
        "estimated_cost": Decimal(data["estimated_cost"]),
        "created_at": created_at,
    }
    data["confirmation_token"] = sign_order(signable, JWT_SECRET)
    return data
