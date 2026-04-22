from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from gateway.deps import get_registry
from gateway.main import create_app
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
    async def get_quote(self, ticker: str) -> QuoteData | None:
        if ticker.upper() == "AAPL":
            return QuoteData(ticker="AAPL", price=Decimal("189.55"))
        return None

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        if ticker.upper() == "AAPL":
            return CompanyProfile(ticker="AAPL", name="Apple Inc")
        return None

    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None:
        return Fundamentals(ticker=ticker.upper(), period=period)

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        return [
            PriceBar(
                timestamp=datetime(2026, 4, 22, tzinfo=timezone.utc),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.5"),
                volume=1000,
            )
        ]

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        if "apple" in query.lower():
            return [SymbolMatch(ticker="AAPL", name="Apple Inc")]
        return []

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        return [
            NewsArticle(
                title="Apple news",
                url="https://n/1",
                source="s",
                published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
            )
        ]

    async def get_estimates(self, ticker: str) -> Estimates | None:
        return None

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        return None


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: ProviderRegistry([FakeProvider()])
    with TestClient(app) as c:
        yield c


def test_quote_route_returns_quote(client):
    r = client.get("/quote/AAPL")
    assert r.status_code == 200
    assert r.json()["ticker"] == "AAPL"


def test_quote_route_404_unknown_symbol(client):
    r = client.get("/quote/ZZZZ")
    assert r.status_code == 404


def test_search_route_returns_matches(client):
    r = client.get("/search", params={"q": "apple", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body[0]["ticker"] == "AAPL"


def test_search_route_empty(client):
    r = client.get("/search", params={"q": "xxxyyyzzz"})
    assert r.status_code == 200
    assert r.json() == []


def test_news_route_returns_articles(client):
    r = client.get("/news", params={"limit": 5})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_profile_route_returns_profile(client):
    r = client.get("/profile/AAPL")
    assert r.status_code == 200
    assert r.json()["name"] == "Apple Inc"


def test_profile_route_404(client):
    r = client.get("/profile/ZZZZ")
    assert r.status_code == 404


def test_price_history_route_returns_bars(client):
    r = client.get("/price-history/AAPL", params={"period": "1M"})
    assert r.status_code == 200
    bars = r.json()
    assert len(bars) == 1
    assert bars[0]["close"] == "100.5"
