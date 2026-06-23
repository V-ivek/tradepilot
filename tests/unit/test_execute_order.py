from datetime import datetime, timedelta, timezone
from decimal import Decimal

from gateway.services.paper_trading import OrderResult
from src.models.order import TOKEN_TTL_SECONDS, new_nonce, sign_order
from src.tools.trading.execute_order import _impl

SECRET = "t-secret"


def _draft_data(**overrides):
    data = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": Decimal("1"),
        "type": "market",
        "limit_price": None,
        "stop_price": None,
        "time_in_force": "day",
        "estimated_cost": Decimal("100"),
        "nonce": new_nonce(),
        "created_at": datetime.now(timezone.utc),
        "mode": "paper",
    }
    data.update(overrides)
    data["confirmation_token"] = sign_order(data, SECRET)
    return data


class FakeGateway:
    def __init__(self, *, result: OrderResult | None = None, raises: Exception | None = None):
        self._result = result
        self._raises = raises

    async def place_order(self, req):
        if self._raises:
            raise self._raises
        return self._result


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


async def test_happy_path_returns_order_result():
    gw = FakeGateway(result=_ok_result())
    data = _draft_data()

    result = await _impl(gw, SECRET, data)

    assert "error" not in result
    assert result["order_id"] == "o-1"
    assert result["mode"] == "paper"


async def test_expired_token_rejected():
    gw = FakeGateway(result=_ok_result())
    data = _draft_data(
        created_at=datetime.now(timezone.utc) - timedelta(seconds=TOKEN_TTL_SECONDS + 5)
    )
    # Re-sign so the hmac matches; TTL check should still reject.
    data["confirmation_token"] = sign_order(data, SECRET)

    result = await _impl(gw, SECRET, data)

    assert result["error"] == "draft expired or tampered"


async def test_tampered_draft_rejected():
    gw = FakeGateway(result=_ok_result())
    data = _draft_data()
    data["qty"] = Decimal("1000")  # mutate without re-signing

    result = await _impl(gw, SECRET, data)

    assert "tampered" in result["error"]


async def test_gateway_raises_returns_error():
    gw = FakeGateway(raises=RuntimeError("alpaca down"))
    data = _draft_data()

    result = await _impl(gw, SECRET, data)

    assert "alpaca down" in result["error"]


async def test_gateway_returns_none_returns_error():
    gw = FakeGateway(result=None)
    data = _draft_data()

    result = await _impl(gw, SECRET, data)

    assert "error" in result


async def test_invalid_draft_shape_returns_error():
    gw = FakeGateway(result=_ok_result())
    data = _draft_data()
    data.pop("symbol")

    result = await _impl(gw, SECRET, data)

    assert "Invalid draft" in result["error"]
