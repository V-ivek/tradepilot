from datetime import datetime, timezone
from decimal import Decimal

from gateway.services.paper_trading import (
    Account,
    OrderRequest,
    OrderResult,
    PortfolioHistory,
    Position,
)


def _roundtrip(model):
    return type(model).model_validate(model.model_dump(mode="json"))


def test_order_request_roundtrip():
    r = OrderRequest(symbol="AAPL", side="buy", qty=Decimal("10"), type="market")
    assert _roundtrip(r) == r


def test_order_result_roundtrip_with_mode_paper():
    r = OrderResult(
        order_id="x",
        symbol="AAPL",
        side="buy",
        qty=Decimal("10"),
        type="market",
        status="filled",
        filled_qty=Decimal("10"),
        filled_avg_price=Decimal("189.55"),
        submitted_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    assert r.mode == "paper"
    assert _roundtrip(r) == r


def test_account_requires_mode_paper_literal():
    a = Account(
        equity=Decimal("100000"),
        cash=Decimal("50000"),
        buying_power=Decimal("50000"),
        day_trade_count=0,
        positions_count=3,
    )
    assert a.mode == "paper"
    dumped = a.model_dump()
    assert dumped["mode"] == "paper"


def test_position_roundtrip():
    p = Position(
        symbol="AAPL",
        qty=Decimal("10"),
        avg_entry_price=Decimal("180"),
        market_value=Decimal("1900"),
        unrealized_pl=Decimal("100"),
        unrealized_plpc=Decimal("0.0555"),
    )
    assert _roundtrip(p) == p


def test_portfolio_history_roundtrip():
    h = PortfolioHistory(
        timestamps=[datetime(2026, 4, 22, tzinfo=timezone.utc)],
        equity=[Decimal("100000")],
        profit_loss=[Decimal("500")],
        base_value=Decimal("99500"),
    )
    assert _roundtrip(h) == h
