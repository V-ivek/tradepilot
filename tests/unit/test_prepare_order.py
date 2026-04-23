from decimal import Decimal

from gateway.models import QuoteData, SymbolMatch
from gateway.services.paper_trading import Account
from src.models.order import OrderDraft, verify_order_token
from src.tools.trading.prepare_order import _impl

SECRET = "t-secret"


class FakeGateway:
    def __init__(
        self,
        *,
        matches: list[SymbolMatch] | None = None,
        quote: QuoteData | None = None,
        account: Account | None = None,
    ):
        self._matches = (
            matches if matches is not None else [SymbolMatch(ticker="AAPL", name="Apple Inc")]
        )
        self._quote = quote or QuoteData(ticker="AAPL", price=Decimal("100"))
        self._account = account or Account(
            equity=Decimal("100000"),
            cash=Decimal("100000"),
            buying_power=Decimal("100000"),
            day_trade_count=0,
            positions_count=0,
        )

    async def search_symbols(self, q, *, limit=5):
        return [
            m for m in self._matches if m.ticker.upper() == q.upper() or q.upper() in m.name.upper()
        ]

    async def get_quote(self, ticker):
        return self._quote

    async def get_account(self):
        return self._account


async def test_happy_path_produces_verifiable_draft():
    gw = FakeGateway()
    result = await _impl(gw, SECRET, symbol="aapl", side="buy", qty="10", type="market")

    assert "error" not in result
    draft = OrderDraft.model_validate(result)
    assert verify_order_token(draft, SECRET) is True
    assert draft.symbol == "AAPL"
    assert draft.estimated_cost == Decimal("1000")
    assert draft.mode == "paper"


async def test_unknown_symbol_returns_error():
    gw = FakeGateway(matches=[])
    result = await _impl(gw, SECRET, symbol="ZZZZ", side="buy", qty="1", type="market")

    assert "error" in result
    assert "Unknown" in result["error"]


async def test_insufficient_buying_power_returns_error():
    gw = FakeGateway(
        account=Account(
            equity=Decimal("50"),
            cash=Decimal("50"),
            buying_power=Decimal("50"),
            day_trade_count=0,
            positions_count=0,
        )
    )
    result = await _impl(gw, SECRET, symbol="AAPL", side="buy", qty="10", type="market")

    assert "error" in result
    assert "Insufficient buying power" in result["error"]


async def test_sell_skips_buying_power_check():
    gw = FakeGateway(
        account=Account(
            equity=Decimal("0"),
            cash=Decimal("0"),
            buying_power=Decimal("0"),
            day_trade_count=0,
            positions_count=0,
        )
    )
    result = await _impl(gw, SECRET, symbol="AAPL", side="sell", qty="1", type="market")

    assert "error" not in result


async def test_limit_order_uses_limit_price_for_estimate():
    gw = FakeGateway()
    result = await _impl(
        gw,
        SECRET,
        symbol="AAPL",
        side="buy",
        qty="10",
        type="limit",
        limit_price="90",
    )

    assert "error" not in result
    assert Decimal(result["estimated_cost"]) == Decimal("900")


async def test_invalid_quantity_returns_error():
    gw = FakeGateway()
    result = await _impl(gw, SECRET, symbol="AAPL", side="buy", qty="0", type="market")

    assert "error" in result
    assert "quantity" in result["error"].lower()


async def test_missing_quote_returns_error():
    class NoQuoteGateway(FakeGateway):
        async def get_quote(self, ticker):
            return None

    gw = NoQuoteGateway()
    result = await _impl(gw, SECRET, symbol="AAPL", side="buy", qty="1", type="market")

    assert "error" in result
    assert "No quote" in result["error"]


async def test_limit_order_without_limit_price_produces_invalid_draft():
    gw = FakeGateway()
    result = await _impl(gw, SECRET, symbol="AAPL", side="buy", qty="1", type="limit")

    # uses quote price for estimate, then draft validation fails (limit_price required)
    assert "error" in result
