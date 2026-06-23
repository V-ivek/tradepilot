import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from alpaca.common.enums import BaseURL
from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus
from alpaca.trading.requests import (
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)

from gateway.services.paper_trading import OrderRequest
from gateway.services.paper_trading_alpaca import (
    LIVE_BASE_URL_DENY,
    PAPER_BASE_URL,
    AlpacaPaperTradingAdapter,
)


def _fake_client(base_url: BaseURL | str = BaseURL.TRADING_PAPER) -> MagicMock:
    c = MagicMock()
    c._base_url = base_url
    return c


def _raw_order(
    *,
    order_id: str = "o-1",
    symbol: str = "AAPL",
    qty: str = "10",
    side: str = "buy",
    type_: str = "market",
    status: AlpacaOrderStatus = AlpacaOrderStatus.FILLED,
    filled_qty: str = "10",
    filled_avg_price: str = "189.55",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=order_id,
        symbol=symbol,
        qty=qty,
        side=SimpleNamespace(value=side),
        type=SimpleNamespace(value=type_),
        status=status,
        filled_qty=filled_qty,
        filled_avg_price=filled_avg_price,
        submitted_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )


def test_construction_with_paper_client_succeeds():
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=_fake_client())
    assert adapter is not None


def test_assert_paper_raises_on_live_url():
    client = _fake_client(base_url=LIVE_BASE_URL_DENY)
    with pytest.raises(RuntimeError, match="live endpoint is architecturally blocked"):
        AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)


def test_assert_paper_raises_on_unknown_url():
    client = _fake_client(base_url="https://fake.alpaca")
    with pytest.raises(RuntimeError, match="not the paper endpoint"):
        AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)


async def test_every_public_method_calls_assert_paper(monkeypatch):
    client = _fake_client()
    client.get_account.return_value = SimpleNamespace(
        equity="1", cash="1", buying_power="1", daytrade_count=0
    )
    client.get_all_positions.return_value = []
    client.get_orders.return_value = []
    client.submit_order.return_value = _raw_order()
    client.cancel_order_by_id.return_value = None
    client.get_portfolio_history.return_value = SimpleNamespace(
        timestamp=[], equity=[], profit_loss=[], base_value=0
    )

    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)
    calls = {"n": 0}
    original = adapter._assert_paper

    def counting():
        calls["n"] += 1
        original()

    monkeypatch.setattr(adapter, "_assert_paper", counting)

    await adapter.get_account()
    await adapter.list_positions()
    await adapter.list_orders()
    await adapter.place_order(
        OrderRequest(symbol="AAPL", side="buy", qty=Decimal("1"), type="market")
    )
    await adapter.cancel_order("o")
    await adapter.get_portfolio_history()

    # get_account calls _to_thread twice (get_account + get_all_positions),
    # each invocation calls _assert_paper. Other methods call once.
    # 2 + 1 + 1 + 1 + 1 + 1 = 7
    assert calls["n"] == 7


async def test_get_account_maps_fields():
    client = _fake_client()
    client.get_account.return_value = SimpleNamespace(
        equity="100000.50",
        cash="50000.25",
        buying_power="50000.25",
        daytrade_count=2,
    )
    client.get_all_positions.return_value = [SimpleNamespace(), SimpleNamespace()]
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    acct = await adapter.get_account()

    assert acct.equity == Decimal("100000.50")
    assert acct.day_trade_count == 2
    assert acct.positions_count == 2
    assert acct.mode == "paper"


async def test_place_market_order_uses_market_request():
    client = _fake_client()
    client.submit_order.return_value = _raw_order()
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    await adapter.place_order(
        OrderRequest(symbol="AAPL", side="buy", qty=Decimal("10"), type="market")
    )

    submitted = client.submit_order.call_args.args[0]
    assert isinstance(submitted, MarketOrderRequest)


async def test_place_limit_order_uses_limit_request():
    client = _fake_client()
    client.submit_order.return_value = _raw_order(type_="limit")
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    await adapter.place_order(
        OrderRequest(
            symbol="AAPL",
            side="buy",
            qty=Decimal("10"),
            type="limit",
            limit_price=Decimal("180"),
        )
    )

    submitted = client.submit_order.call_args.args[0]
    assert isinstance(submitted, LimitOrderRequest)
    assert submitted.limit_price == 180.0


async def test_place_stop_order_uses_stop_request():
    client = _fake_client()
    client.submit_order.return_value = _raw_order(type_="stop")
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    await adapter.place_order(
        OrderRequest(
            symbol="AAPL",
            side="sell",
            qty=Decimal("10"),
            type="stop",
            stop_price=Decimal("170"),
        )
    )

    submitted = client.submit_order.call_args.args[0]
    assert isinstance(submitted, StopOrderRequest)


async def test_place_stop_limit_order_uses_stop_limit_request():
    client = _fake_client()
    client.submit_order.return_value = _raw_order(type_="stop_limit")
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    await adapter.place_order(
        OrderRequest(
            symbol="AAPL",
            side="sell",
            qty=Decimal("10"),
            type="stop_limit",
            limit_price=Decimal("171"),
            stop_price=Decimal("170"),
        )
    )

    submitted = client.submit_order.call_args.args[0]
    assert isinstance(submitted, StopLimitOrderRequest)


async def test_place_order_result_carries_mode_paper():
    client = _fake_client()
    client.submit_order.return_value = _raw_order()
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    result = await adapter.place_order(
        OrderRequest(symbol="AAPL", side="buy", qty=Decimal("1"), type="market")
    )

    assert result.mode == "paper"
    assert result.status == "filled"


async def test_list_orders_maps_query_status():
    client = _fake_client()
    client.get_orders.return_value = [_raw_order(order_id=str(uuid.uuid4()))]
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    orders = await adapter.list_orders(status="filled")

    assert len(orders) == 1
    assert orders[0].mode == "paper"


async def test_portfolio_history_maps_arrays():
    client = _fake_client()
    client.get_portfolio_history.return_value = SimpleNamespace(
        timestamp=[1714000000, 1714086400],
        equity=["100000", "101000"],
        profit_loss=["0", "1000"],
        base_value="100000",
    )
    adapter = AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)

    h = await adapter.get_portfolio_history("1M")

    assert len(h.timestamps) == 2
    assert h.equity[1] == Decimal("101000")
    assert h.base_value == Decimal("100000")


def test_paper_url_constant_matches_alpaca_enum():
    assert PAPER_BASE_URL == BaseURL.TRADING_PAPER.value
    assert LIVE_BASE_URL_DENY == BaseURL.TRADING_LIVE.value
