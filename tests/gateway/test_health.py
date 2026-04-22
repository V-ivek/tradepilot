import pytest
from fastapi.testclient import TestClient

from gateway.deps import get_registry
from gateway.main import create_app
from gateway.providers.registry import ProviderRegistry


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: ProviderRegistry([])
    with TestClient(app) as c:
        yield c


def test_health_reports_paper_mode_and_empty_providers(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["trading_mode"] == "paper"
    assert body["providers"] == []


def test_health_lists_active_provider_class_names():
    from gateway.providers.base import DataProvider

    class _Fake(DataProvider):
        async def get_quote(self, ticker):
            return None

        async def get_company_profile(self, ticker):
            return None

        async def get_fundamentals(self, ticker, *, statement="all", period="annual"):
            return None

        async def get_price_history(self, ticker, *, period="1M"):
            return []

        async def search_symbols(self, query, *, limit=10):
            return []

        async def get_news(self, *, query=None, tickers=None, limit=20):
            return []

        async def get_estimates(self, ticker):
            return None

        async def get_analyst_data(self, ticker):
            return None

    app = create_app()
    app.dependency_overrides[get_registry] = lambda: ProviderRegistry([_Fake()])
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.json()["providers"] == ["_Fake"]
