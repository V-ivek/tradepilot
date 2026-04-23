from datetime import datetime, timezone
from decimal import Decimal

from gateway.services.paper_trading import (
    Account,
    OrderResult,
    PortfolioHistory,
    Position,
)


class FakeGateway:
    def __init__(self, *, empty: bool = False):
        self.empty = empty

    async def get_account(self):
        if self.empty:
            return None
        return Account(
            equity=Decimal("100000"),
            cash=Decimal("50000"),
            buying_power=Decimal("50000"),
            day_trade_count=0,
            positions_count=1,
        )

    async def list_positions(self):
        if self.empty:
            return []
        return [
            Position(
                symbol="AAPL",
                qty=Decimal("10"),
                avg_entry_price=Decimal("180"),
                market_value=Decimal("1900"),
                unrealized_pl=Decimal("100"),
                unrealized_plpc=Decimal("0.0555"),
            )
        ]

    async def list_orders(self, status=None):
        if self.empty:
            return []
        return [
            OrderResult(
                order_id="o",
                symbol="AAPL",
                side="buy",
                qty=Decimal("10"),
                type="market",
                status="filled",
                filled_qty=Decimal("10"),
                filled_avg_price=Decimal("180"),
                submitted_at=datetime.now(timezone.utc),
            )
        ]

    async def get_portfolio_history(self, period="1M"):
        if self.empty:
            return None
        return PortfolioHistory(
            timestamps=[datetime.now(timezone.utc)],
            equity=[Decimal("100000")],
            profit_loss=[Decimal("0")],
            base_value=Decimal("100000"),
        )


async def test_get_account_tool():
    from src.tools.account.get_account import _impl

    result = await _impl(FakeGateway())
    assert result["cash"] == "50000"
    assert result["mode"] == "paper"


async def test_get_account_empty():
    from src.tools.account.get_account import _impl

    assert await _impl(FakeGateway(empty=True)) == {}


async def test_list_positions_tool():
    from src.tools.account.list_positions import _impl

    positions = await _impl(FakeGateway())
    assert positions[0]["symbol"] == "AAPL"


async def test_list_orders_tool():
    from src.tools.account.list_orders import _impl

    orders = await _impl(FakeGateway())
    assert orders[0]["status"] == "filled"


async def test_list_orders_with_status():
    from src.tools.account.list_orders import _impl

    orders = await _impl(FakeGateway(), status="filled")
    assert len(orders) == 1


async def test_get_portfolio_history_tool():
    from src.tools.account.get_portfolio_history import _impl

    history = await _impl(FakeGateway(), "1M")
    assert history["base_value"] == "100000"


async def test_get_portfolio_history_empty():
    from src.tools.account.get_portfolio_history import _impl

    assert await _impl(FakeGateway(empty=True)) == {}
