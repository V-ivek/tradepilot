from decimal import Decimal

from gateway.services.paper_trading import OrderRequest, PaperTradingService
from tests.gateway.fakes.paper_trading import FakePaperTradingAdapter


async def test_fake_satisfies_protocol():
    adapter = FakePaperTradingAdapter()
    assert isinstance(adapter, PaperTradingService)


async def test_buy_reduces_cash_and_opens_position():
    adapter = FakePaperTradingAdapter(starting_cash=Decimal("1000"), fill_price=Decimal("100"))
    result = await adapter.place_order(
        OrderRequest(symbol="AAPL", side="buy", qty=Decimal("2"), type="market")
    )

    assert result.status == "filled"
    assert result.filled_qty == Decimal("2")
    acct = await adapter.get_account()
    assert acct.cash == Decimal("800")
    positions = await adapter.list_positions()
    assert len(positions) == 1
    assert positions[0].qty == Decimal("2")


async def test_sell_clears_position_when_qty_matches():
    adapter = FakePaperTradingAdapter(starting_cash=Decimal("1000"), fill_price=Decimal("100"))
    await adapter.place_order(
        OrderRequest(symbol="AAPL", side="buy", qty=Decimal("2"), type="market")
    )
    await adapter.place_order(
        OrderRequest(symbol="AAPL", side="sell", qty=Decimal("2"), type="market")
    )

    assert await adapter.list_positions() == []
    assert (await adapter.get_account()).cash == Decimal("1000")


async def test_cancel_marks_order_canceled():
    adapter = FakePaperTradingAdapter()
    order = await adapter.place_order(
        OrderRequest(symbol="AAPL", side="buy", qty=Decimal("1"), type="market")
    )
    await adapter.cancel_order(order.order_id)
    orders = await adapter.list_orders()
    assert orders[0].status == "canceled"


async def test_list_orders_filters_by_status():
    adapter = FakePaperTradingAdapter()
    await adapter.place_order(
        OrderRequest(symbol="AAPL", side="buy", qty=Decimal("1"), type="market")
    )
    filled = await adapter.list_orders(status="filled")
    canceled = await adapter.list_orders(status="canceled")
    assert len(filled) == 1
    assert canceled == []


async def test_portfolio_history_shape():
    adapter = FakePaperTradingAdapter()
    history = await adapter.get_portfolio_history("1M")
    assert len(history.timestamps) == len(history.equity) == len(history.profit_loss)
