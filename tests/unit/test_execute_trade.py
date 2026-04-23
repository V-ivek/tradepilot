from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from gateway.services.paper_trading import OrderResult
from src.agent.nodes.execute_trade import execute_trade_node
from src.agent.state import AssistantState
from src.models.order import TOKEN_TTL_SECONDS, new_nonce, sign_order

SECRET = "t-secret"


def _draft_data(**overrides) -> dict:
    data = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": "1",
        "type": "market",
        "limit_price": None,
        "stop_price": None,
        "time_in_force": "day",
        "estimated_cost": "100",
        "nonce": new_nonce(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
    }
    data.update(overrides)
    signable = {
        **data,
        "qty": Decimal(data["qty"]),
        "estimated_cost": Decimal(data["estimated_cost"]),
        "created_at": datetime.fromisoformat(data["created_at"]),
    }
    data["confirmation_token"] = sign_order(signable, SECRET)
    return data


def _ok_result() -> OrderResult:
    return OrderResult(
        order_id="o-1",
        symbol="AAPL",
        side="buy",
        qty=Decimal("1"),
        type="market",
        status="filled",
        filled_qty=Decimal("1"),
        filled_avg_price=Decimal("100"),
        submitted_at=datetime.now(timezone.utc),
    )


def _settings():
    class _S:
        jwt_secret = SECRET

    return _S()


async def _run(state, *, result=None, raises=None):
    gw = AsyncMock()
    if raises:
        gw.place_order = AsyncMock(side_effect=raises)
    else:
        gw.place_order = AsyncMock(return_value=result)
    with (
        patch("src.agent.nodes.execute_trade.get_gateway_client", return_value=gw),
        patch("src.agent.nodes.execute_trade.get_settings", return_value=_settings()),
    ):
        return await execute_trade_node(state)


async def test_no_pending_trade_emits_text():
    out = await _run({})
    assert out["blocks"][0]["content"] == "No order to confirm."


async def test_expired_token_rejected_and_state_cleared():
    expired_data = _draft_data(
        created_at=(
            datetime.now(timezone.utc) - timedelta(seconds=TOKEN_TTL_SECONDS + 5)
        ).isoformat()
    )
    state: AssistantState = {
        "pending_trade": expired_data,
        "awaiting_confirmation": True,
    }

    out = await _run(state, result=_ok_result())

    assert "expired" in out["blocks"][0]["content"].lower()
    assert out["pending_trade"] is None
    assert out["awaiting_confirmation"] is False


async def test_tampered_draft_rejected():
    data = _draft_data()
    data["qty"] = "1000"  # mutate without re-signing
    state = {"pending_trade": data, "awaiting_confirmation": True}

    out = await _run(state, result=_ok_result())

    content = out["blocks"][0]["content"].lower()
    assert "expired" in content or "tampered" in content
    assert out["pending_trade"] is None


async def test_gateway_raises_returns_text():
    state = {"pending_trade": _draft_data(), "awaiting_confirmation": True}
    out = await _run(state, raises=RuntimeError("alpaca down"))

    assert "Order failed" in out["blocks"][0]["content"]
    assert out["pending_trade"] is None


async def test_gateway_returns_none_returns_text():
    state = {"pending_trade": _draft_data(), "awaiting_confirmation": True}
    out = await _run(state, result=None)

    assert "Order failed" in out["blocks"][0]["content"]


async def test_happy_path_emits_order_result_and_clears_state():
    state = {"pending_trade": _draft_data(), "awaiting_confirmation": True}
    out = await _run(state, result=_ok_result())

    result_block = next(b for b in out["blocks"] if b.get("type") == "order_result")
    assert result_block["status"] == "filled"
    assert result_block["mode"] == "paper"
    assert out["pending_trade"] is None
    assert out["awaiting_confirmation"] is False


async def test_invalid_draft_shape_emits_text():
    data = _draft_data()
    data.pop("symbol")
    state = {"pending_trade": data, "awaiting_confirmation": True}

    out = await _run(state, result=_ok_result())

    assert "Invalid pending order" in out["blocks"][0]["content"]
    assert out["pending_trade"] is None
