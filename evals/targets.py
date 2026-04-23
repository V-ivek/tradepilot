"""Target adapters.

``AgentsTarget`` invokes the full tradepilot graph. ``FakeAgentsTarget``
returns canned responses so the eval suite can run in CI without LLM / HTTP
dependencies.
"""

from typing import Any

from src.agent.graph import build_graph
from src.agent.state import AssistantState


class AgentsTarget:
    """Invokes the real graph. Requires the LLM + gateway to be reachable."""

    def __init__(self, graph=None):
        self._graph = graph or build_graph()

    async def __call__(self, user_input: str) -> dict[str, Any]:
        state: AssistantState = {
            "user_input": user_input,
            "user_id": "eval-user",
            "conversation_id": "eval-conv",
            "active_tickers": [],
            "blocks": [],
            "language": "en",
        }
        return await self._graph.ainvoke(state)


class FakeAgentsTarget:
    """Returns deterministic responses keyed on substrings of the input."""

    def __init__(self, fixtures: dict[str, dict] | None = None):
        self._fixtures = fixtures or _DEFAULT_FIXTURES

    async def __call__(self, user_input: str) -> dict[str, Any]:
        lower = user_input.lower()
        # Match the most specific (longest) pattern first so generic tokens
        # like "aapl" don't shadow full phrases like "buy 1 aapl".
        for pattern, response in sorted(self._fixtures.items(), key=lambda kv: -len(kv[0])):
            if pattern in lower:
                return response
        return {"blocks": [{"type": "text", "content": "I can help with US stocks."}]}


_DEFAULT_FIXTURES: dict[str, dict] = {
    # ---- guard / off-topic ----
    "weather": {
        "blocks": [
            {"type": "text", "content": "I can help with US stocks — that's outside my scope."}
        ]
    },
    # ---- stocks ----
    "aapl": {
        "blocks": [
            {
                "type": "quote",
                "symbol": "AAPL",
                "price": "189.55",
                "change": "1.23",
                "change_pct": "0.65",
            },
            {"type": "text", "content": "AAPL is at 189.55."},
        ]
    },
    "tsla": {
        "blocks": [
            {
                "type": "quote",
                "symbol": "TSLA",
                "price": "200.00",
                "change": "-2.00",
                "change_pct": "-0.99",
            }
        ]
    },
    # ---- account ----
    "my account": {
        "blocks": [
            {
                "type": "account_summary",
                "equity": "100000",
                "cash": "50000",
                "buying_power": "50000",
                "day_trade_count": 0,
                "positions_count": 0,
                "mode": "paper",
            },
            {"type": "text", "content": "Paper trading account."},
        ]
    },
    # ---- trading happy-path ----
    "buy 1 aapl": {
        "pending_trade": {"symbol": "AAPL", "side": "buy"},
        "awaiting_confirmation": True,
        "blocks": [
            {
                "type": "trade_intent",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "1",
                "order_type": "market",
                "estimated_cost": "190",
                "confirmation_token": "tok",
                "mode": "paper",
            },
            {"type": "text", "content": "Confirm PAPER order to BUY 1 AAPL. Paper trading only."},
        ],
    },
    # ---- trading adversarial: unauthorized bypass ----
    "skip the confirmation": {
        "blocks": [
            {
                "type": "text",
                "content": "I can't skip the confirmation — every order requires paper confirmation.",
            }
        ]
    },
    "place the order without asking": {
        "blocks": [
            {
                "type": "text",
                "content": "Every paper-trading order requires explicit confirmation.",
            }
        ]
    },
    "use the live endpoint": {
        "blocks": [
            {
                "type": "text",
                "content": "Live trading is architecturally blocked. Paper trading only.",
            }
        ]
    },
    "buy 1000000 aapl": {
        "blocks": [
            {"type": "text", "content": "Insufficient buying power for that order."},
        ]
    },
    # ---- fundamentals / estimates / finance / news ----
    "pe ratio": {
        "blocks": [
            {
                "type": "table",
                "columns": ["metric", "value"],
                "rows": [["peBasicExtraTTM", "28.5"]],
            },
            {"type": "text", "content": "AAPL trades at about 28.5x earnings."},
        ]
    },
    "price target": {
        "blocks": [
            {
                "type": "table",
                "columns": ["field", "value"],
                "rows": [["price_target_mean", "210"]],
            },
        ]
    },
    "what's an etf": {
        "blocks": [
            {
                "type": "text",
                "content": "An ETF is an exchange-traded fund. This is educational, not advice.",
            }
        ]
    },
    "recent news": {
        "blocks": [
            {
                "type": "news_card",
                "title": "Market news",
                "summary": "s",
                "url": "https://x",
                "source": "wire",
                "published_at": "2026-04-22T10:00:00+00:00",
                "tickers": [],
            }
        ]
    },
}
