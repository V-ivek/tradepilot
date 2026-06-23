from decimal import Decimal

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
from gateway.providers.base import DataProvider
from gateway.providers.registry import ProviderRegistry


class FakeProvider(DataProvider):
    def __init__(
        self,
        *,
        quote: QuoteData | None = None,
        raises: Exception | None = None,
        news: list[NewsArticle] | None = None,
        news_raises: Exception | None = None,
    ):
        self.quote = quote
        self.raises = raises
        self.news = news
        self.news_raises = news_raises
        self.calls: dict[str, int] = {"get_quote": 0, "get_news": 0}

    async def get_quote(self, ticker: str) -> QuoteData | None:
        self.calls["get_quote"] += 1
        if self.raises:
            raise self.raises
        return self.quote

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        return None

    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None:
        return None

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        return []

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        return []

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        self.calls["get_news"] += 1
        if self.news_raises:
            raise self.news_raises
        return self.news or []

    async def get_estimates(self, ticker: str) -> Estimates | None:
        return None

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        return None


def _quote(price: str) -> QuoteData:
    return QuoteData(ticker="AAPL", price=Decimal(price))


async def test_first_provider_returns_data_subsequent_not_called():
    first = FakeProvider(quote=_quote("100"))
    second = FakeProvider(quote=_quote("200"))
    reg = ProviderRegistry([first, second])

    result = await reg.get_quote("AAPL")

    assert result == _quote("100")
    assert first.calls["get_quote"] == 1
    assert second.calls["get_quote"] == 0


async def test_first_returns_none_second_called():
    first = FakeProvider(quote=None)
    second = FakeProvider(quote=_quote("200"))
    reg = ProviderRegistry([first, second])

    result = await reg.get_quote("AAPL")

    assert result == _quote("200")
    assert first.calls["get_quote"] == 1
    assert second.calls["get_quote"] == 1


async def test_first_raises_warning_logged_second_called(caplog):
    first = FakeProvider(raises=RuntimeError("boom"))
    second = FakeProvider(quote=_quote("200"))
    reg = ProviderRegistry([first, second])

    with caplog.at_level("WARNING"):
        result = await reg.get_quote("AAPL")

    assert result == _quote("200")
    assert any(
        "boom" in rec.getMessage() or "FakeProvider" in rec.getMessage() for rec in caplog.records
    )


async def test_all_providers_fail_returns_none():
    first = FakeProvider(quote=None)
    second = FakeProvider(quote=None)
    reg = ProviderRegistry([first, second])

    result = await reg.get_quote("AAPL")

    assert result is None


async def test_empty_list_return_treated_as_fallthrough_for_list_methods():
    first = FakeProvider(news=[])
    article = NewsArticle(
        title="hi",
        url="https://x",
        source="s",
        published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    second = FakeProvider(news=[article])
    reg = ProviderRegistry([first, second])

    result = await reg.get_news(query="foo")

    assert result == [article]
    assert first.calls["get_news"] == 1
    assert second.calls["get_news"] == 1


async def test_all_list_providers_empty_returns_empty_list():
    first = FakeProvider(news=[])
    second = FakeProvider(news=[])
    reg = ProviderRegistry([first, second])

    result = await reg.get_news(query="foo")

    assert result == []


async def test_list_method_exception_fallthrough(caplog):
    first = FakeProvider(news_raises=RuntimeError("api-down"))
    article = NewsArticle(
        title="hi",
        url="https://x",
        source="s",
        published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    second = FakeProvider(news=[article])
    reg = ProviderRegistry([first, second])

    with caplog.at_level("WARNING"):
        result = await reg.get_news(query="foo")

    assert result == [article]
