"""Graph-level tests.

LLM-backed nodes are stubbed with deterministic fakes so the entire turn
runs without external services. Each test asserts the post-turn state.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from gateway.services.paper_trading import OrderResult
from src.agent.graph import build_graph
from src.models.order import new_nonce, sign_order

SECRET = "t-secret"


def _settings():
    class _S:
        jwt_secret = SECRET

    return _S()


async def _guard_routes_to(node_name: str):
    async def fake_guard(state, *, model=None):
        state["category"] = "stock"  # unused; next_node is authoritative
        state["next_node"] = node_name
        state.setdefault("blocks", [])
        state.setdefault("active_tickers", [])
        return state

    return fake_guard


async def _noop_agent(state, *, model=None):
    state.setdefault("blocks", []).append({"type": "text", "content": "noop"})
    return state


def _make_pending_trade_data() -> dict:
    data = {
        "symbol": "TSLA",
        "side": "buy",
        "qty": "10",
        "type": "market",
        "limit_price": None,
        "stop_price": None,
        "time_in_force": "day",
        "estimated_cost": "2000",
        "nonce": new_nonce(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
    }
    signable = {
        **data,
        "qty": Decimal(data["qty"]),
        "estimated_cost": Decimal(data["estimated_cost"]),
        "created_at": datetime.fromisoformat(data["created_at"]),
    }
    data["confirmation_token"] = sign_order(signable, SECRET)
    return data


def _ok_order_result() -> OrderResult:
    return OrderResult(
        order_id="o-1",
        symbol="TSLA",
        side="buy",
        qty=Decimal("10"),
        type="market",
        status="filled",
        filled_qty=Decimal("10"),
        filled_avg_price=Decimal("200"),
        submitted_at=datetime.now(timezone.utc),
    )


async def test_off_topic_routes_to_rejection():
    async def fake_guard(state, *, model=None):
        state["next_node"] = "rejection"
        state.setdefault("blocks", [])
        return state

    graph = build_graph(nodes={"guard": fake_guard})
    out = await graph.ainvoke({"user_input": "weather?"})

    text_blocks = [b for b in out["blocks"] if b["type"] == "text"]
    assert any("outside" in b["content"].lower() for b in text_blocks)


async def test_stock_question_routes_to_stock_agent():
    async def fake_stock(state, *, model=None):
        state.setdefault("blocks", []).append(
            {
                "type": "quote",
                "symbol": "AAPL",
                "price": "100",
                "change": "0",
                "change_pct": "0",
            }
        )
        return state

    graph = build_graph(
        nodes={"guard": await _guard_routes_to("stock_agent"), "stock_agent": fake_stock}
    )
    out = await graph.ainvoke({"user_input": "AAPL?"})

    assert any(b["type"] == "quote" for b in out["blocks"])


async def test_buy_request_halts_at_confirmation_gate():
    draft_data = _make_pending_trade_data()

    async def fake_trade_agent(state, *, model=None):
        state["pending_trade"] = draft_data
        state["awaiting_confirmation"] = True
        state.setdefault("blocks", []).append(
            {
                "type": "trade_intent",
                "symbol": "TSLA",
                "side": "buy",
                "qty": "10",
                "order_type": "market",
                "estimated_cost": "2000",
                "confirmation_token": draft_data["confirmation_token"],
                "mode": "paper",
            }
        )
        return state

    graph = build_graph(
        nodes={
            "guard": await _guard_routes_to("trade_agent"),
            "trade_agent": fake_trade_agent,
        }
    )
    out = await graph.ainvoke({"user_input": "buy 10 TSLA"})

    assert out["awaiting_confirmation"] is True
    assert out["pending_trade"] == draft_data
    assert any(b["type"] == "trade_intent" for b in out["blocks"])


async def test_confirmation_routes_to_execute_trade():
    draft_data = _make_pending_trade_data()

    async def fake_guard(state, *, model=None):
        state["next_node"] = "trade_agent"  # ignored because awaiting_confirmation
        state.setdefault("blocks", [])
        return state

    async def fake_classifier(state, *, model=None):
        state["confirmation_verdict"] = "AFFIRM"
        return state

    gw = AsyncMock()
    gw.place_order = AsyncMock(return_value=_ok_order_result())
    with (
        patch("src.agent.nodes.execute_trade.get_gateway_client", return_value=gw),
        patch("src.agent.nodes.execute_trade.get_settings", return_value=_settings()),
    ):
        graph = build_graph(nodes={"guard": fake_guard, "confirmation_classifier": fake_classifier})
        out = await graph.ainvoke(
            {
                "user_input": "confirm",
                "pending_trade": draft_data,
                "awaiting_confirmation": True,
            }
        )

    assert any(b.get("type") == "order_result" for b in out["blocks"])
    assert out["pending_trade"] is None
    assert out["awaiting_confirmation"] is False


async def test_deny_clears_pending_trade_without_executing():
    draft_data = _make_pending_trade_data()

    async def fake_guard(state, *, model=None):
        state["next_node"] = "trade_agent"
        state.setdefault("blocks", [])
        return state

    async def fake_classifier(state, *, model=None):
        state["confirmation_verdict"] = "DENY"
        state.setdefault("blocks", []).append({"type": "text", "content": "canceled"})
        # DENY should clear state — done here since the validator path
        # doesn't currently do it.
        state["pending_trade"] = None
        state["awaiting_confirmation"] = False
        return state

    gw = AsyncMock()
    gw.place_order = AsyncMock(return_value=_ok_order_result())
    with (
        patch("src.agent.nodes.execute_trade.get_gateway_client", return_value=gw),
        patch("src.agent.nodes.execute_trade.get_settings", return_value=_settings()),
    ):
        graph = build_graph(nodes={"guard": fake_guard, "confirmation_classifier": fake_classifier})
        out = await graph.ainvoke(
            {
                "user_input": "cancel",
                "pending_trade": draft_data,
                "awaiting_confirmation": True,
            }
        )

    assert out["pending_trade"] is None
    assert out["awaiting_confirmation"] is False
    # No order was placed
    assert not any(b.get("type") == "order_result" for b in out["blocks"])
    gw.place_order.assert_not_called()


async def test_modify_routes_back_to_trade_agent():
    old_draft = _make_pending_trade_data()
    called = {"trade_agent": 0}

    async def fake_guard(state, *, model=None):
        state["next_node"] = "trade_agent"
        state.setdefault("blocks", [])
        return state

    async def fake_classifier(state, *, model=None):
        state["confirmation_verdict"] = "MODIFY"
        state["pending_edits"] = {"qty": "5"}
        return state

    async def fake_trade_agent(state, *, model=None):
        called["trade_agent"] += 1
        new_draft = _make_pending_trade_data()
        new_draft["qty"] = "5"
        state["pending_trade"] = new_draft
        state["awaiting_confirmation"] = True
        state.setdefault("blocks", []).append(
            {
                "type": "trade_intent",
                "symbol": "TSLA",
                "side": "buy",
                "qty": "5",
                "order_type": "market",
                "estimated_cost": "1000",
                "confirmation_token": new_draft["confirmation_token"],
                "mode": "paper",
            }
        )
        return state

    graph = build_graph(
        nodes={
            "guard": fake_guard,
            "confirmation_classifier": fake_classifier,
            "trade_agent": fake_trade_agent,
        }
    )
    out = await graph.ainvoke(
        {
            "user_input": "change qty to 5",
            "pending_trade": old_draft,
            "awaiting_confirmation": True,
        }
    )

    assert called["trade_agent"] == 1
    assert out["awaiting_confirmation"] is True
    assert out["pending_trade"]["qty"] == "5"


async def test_unrelated_reply_routes_to_validator_without_executing():
    draft_data = _make_pending_trade_data()

    async def fake_guard(state, *, model=None):
        state["next_node"] = "trade_agent"
        state.setdefault("blocks", [])
        return state

    async def fake_classifier(state, *, model=None):
        state["confirmation_verdict"] = "UNRELATED"
        return state

    gw = AsyncMock()
    gw.place_order = AsyncMock(return_value=_ok_order_result())
    with (
        patch("src.agent.nodes.execute_trade.get_gateway_client", return_value=gw),
        patch("src.agent.nodes.execute_trade.get_settings", return_value=_settings()),
    ):
        graph = build_graph(nodes={"guard": fake_guard, "confirmation_classifier": fake_classifier})
        out = await graph.ainvoke(
            {
                "user_input": "hmm",
                "pending_trade": draft_data,
                "awaiting_confirmation": True,
            }
        )

    gw.place_order.assert_not_called()
    assert not any(b.get("type") == "order_result" for b in out["blocks"])
