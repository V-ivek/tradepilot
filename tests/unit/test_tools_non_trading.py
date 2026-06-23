from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gateway.models import (
    AnalystData,
    CompanyProfile,
    Estimates,
    Fundamentals,
    NewsArticle,
    PriceBar,
    QuoteData,
    SymbolMatch,
)


class FakeGateway:
    def __init__(self, *, empty: bool = False):
        self.empty = empty
        self._health = {"status": "ok", "trading_mode": "paper"}

    async def get_quote(self, ticker: str) -> QuoteData | None:
        if self.empty:
            return None
        return QuoteData(ticker=ticker.upper(), price=Decimal("100"))

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        if self.empty:
            return []
        return [SymbolMatch(ticker="AAPL", name="Apple Inc")]

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        if self.empty:
            return []
        return [
            PriceBar(
                timestamp=datetime(2026, 4, 22, tzinfo=timezone.utc),
                open=Decimal("1"),
                high=Decimal("2"),
                low=Decimal("0.5"),
                close=Decimal("1.5"),
                volume=100,
            )
        ]

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        if self.empty:
            return []
        return [
            NewsArticle(
                title="Headline",
                url="https://x",
                source="s",
                published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
                tickers=tickers or [],
            )
        ]

    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        return None if self.empty else CompanyProfile(ticker=ticker.upper(), name="X")

    async def get_fundamentals(self, ticker: str, **kw) -> Fundamentals | None:
        return (
            None
            if self.empty
            else Fundamentals(ticker=ticker.upper(), period=kw.get("period", "annual"))
        )

    async def get_estimates(self, ticker: str) -> Estimates | None:
        return (
            None
            if self.empty
            else Estimates(
                ticker=ticker.upper(),
                eps_estimate=Decimal("2.1"),
                price_target_mean=Decimal("210"),
                recommendations={"buy": 5, "hold": 3},
                analyst_count=8,
            )
        )

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        return None if self.empty else AnalystData(ticker=ticker.upper(), buy=5, sell=1)

    async def health(self):
        return self._health


@pytest.fixture
def gw():
    return FakeGateway()


@pytest.fixture
def gw_empty():
    return FakeGateway(empty=True)


# ---- stocks --------------------------------------------------------------


async def test_lookup_stock_returns_dict(gw):
    from src.tools.stocks.lookup import _impl

    assert (await _impl(gw, "AAPL"))["price"] == "100"


async def test_lookup_stock_empty_on_none(gw_empty):
    from src.tools.stocks.lookup import _impl

    assert await _impl(gw_empty, "AAPL") == {}


async def test_search_stock(gw):
    from src.tools.stocks.search import _impl

    matches = await _impl(gw, "apple")
    assert matches[0]["ticker"] == "AAPL"


async def test_price_history(gw):
    from src.tools.stocks.price_history import _impl

    bars = await _impl(gw, "AAPL", "1M")
    assert len(bars) == 1


async def test_stock_news_passes_ticker(gw):
    from src.tools.stocks.stock_news import _impl

    articles = await _impl(gw, "AAPL", 5)
    assert articles[0]["tickers"] == ["AAPL"]


# ---- news ----------------------------------------------------------------


async def test_search_news(gw):
    from src.tools.news.alpaca_news import _impl

    articles = await _impl(gw, query="AI")
    assert len(articles) == 1


async def test_trending_news(gw):
    from src.tools.news.trending import _impl

    articles = await _impl(gw, limit=3)
    assert len(articles) == 1


# ---- market --------------------------------------------------------------


async def test_market_status_returns_dict(gw):
    from src.tools.market.status import _impl

    status = await _impl(gw)
    assert status["known"] is False
    assert "note" in status


# ---- fundamentals --------------------------------------------------------


@pytest.mark.parametrize(
    "module_path",
    [
        "src.tools.fundamentals.ratios",
        "src.tools.fundamentals.statements",
        "src.tools.fundamentals.shares",
        "src.tools.fundamentals.filings",
        "src.tools.fundamentals.segments",
    ],
)
async def test_fundamentals_tools(gw, module_path):
    import importlib

    mod = importlib.import_module(module_path)
    result = await mod._impl(gw, "AAPL")
    assert result["ticker"] == "AAPL"


async def test_fundamentals_analyst(gw):
    from src.tools.fundamentals.analyst import _impl

    result = await _impl(gw, "AAPL")
    assert result["buy"] == 5


@pytest.mark.parametrize(
    "module_path",
    [
        "src.tools.fundamentals.ratios",
        "src.tools.fundamentals.statements",
        "src.tools.fundamentals.analyst",
        "src.tools.fundamentals.shares",
        "src.tools.fundamentals.filings",
        "src.tools.fundamentals.segments",
    ],
)
async def test_fundamentals_tools_empty(gw_empty, module_path):
    import importlib

    mod = importlib.import_module(module_path)
    assert await mod._impl(gw_empty, "AAPL") == {}


# ---- estimates -----------------------------------------------------------


async def test_earnings(gw):
    from src.tools.estimates.earnings import _impl

    result = await _impl(gw, "AAPL")
    assert result["eps_estimate"] == "2.1"


async def test_recommendations(gw):
    from src.tools.estimates.recommendations import _impl

    result = await _impl(gw, "AAPL")
    assert result["recommendations"]["buy"] == 5


async def test_targets(gw):
    from src.tools.estimates.targets import _impl

    result = await _impl(gw, "AAPL")
    assert result["price_target_mean"] == "210"


@pytest.mark.parametrize(
    "module_path",
    [
        "src.tools.estimates.earnings",
        "src.tools.estimates.recommendations",
        "src.tools.estimates.targets",
    ],
)
async def test_estimates_tools_empty(gw_empty, module_path):
    import importlib

    mod = importlib.import_module(module_path)
    assert await mod._impl(gw_empty, "AAPL") == {}
