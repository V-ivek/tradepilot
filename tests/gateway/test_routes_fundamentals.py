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
        return None

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        return None

    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None:
        if ticker.upper() == "AAPL":
            return Fundamentals(
                ticker="AAPL",
                period=period,
                metrics={"peRatio": Decimal("28.5")},
            )
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
        return []

    async def get_estimates(self, ticker: str) -> Estimates | None:
        if ticker.upper() == "AAPL":
            return Estimates(ticker="AAPL", price_target_mean=Decimal("210"))
        return None

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        if ticker.upper() == "AAPL":
            return AnalystData(ticker="AAPL", buy=5, hold=3, sell=1)
        return None


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: ProviderRegistry([FakeProvider()])
    with TestClient(app) as c:
        yield c


def test_fundamentals_route_returns_data(client):
    r = client.get("/fundamentals/AAPL", params={"statement": "income", "period": "quarterly"})
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["period"] == "quarterly"


def test_fundamentals_route_404(client):
    r = client.get("/fundamentals/ZZZZ")
    assert r.status_code == 404


def test_estimates_route_returns_data(client):
    r = client.get("/estimates/AAPL")
    assert r.status_code == 200
    assert r.json()["price_target_mean"] == "210"


def test_estimates_route_404(client):
    r = client.get("/estimates/ZZZZ")
    assert r.status_code == 404


def test_analyst_route_returns_data(client):
    r = client.get("/analyst/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["buy"] == 5
    assert body["sell"] == 1


def test_analyst_route_404(client):
    r = client.get("/analyst/ZZZZ")
    assert r.status_code == 404
