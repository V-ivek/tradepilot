import httpx
import pytest

from gateway.config import get_settings
from gateway.providers.alpaca import AlpacaProvider
from gateway.providers.factory import get_default_registry
from gateway.providers.finnhub import FinnhubProvider


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


async def test_only_providers_with_keys_are_registered(monkeypatch, client):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "")
    monkeypatch.setenv("FINNHUB_API_KEY", "fnh-key")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "")
    get_settings.cache_clear()

    reg = get_default_registry(client)

    assert len(reg.providers) == 1
    assert isinstance(reg.providers[0], FinnhubProvider)


async def test_alpaca_registered_when_both_keys_set(monkeypatch, client):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "s")
    monkeypatch.setenv("FINNHUB_API_KEY", "")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "")
    get_settings.cache_clear()

    reg = get_default_registry(client)

    assert len(reg.providers) == 1
    assert isinstance(reg.providers[0], AlpacaProvider)


async def test_all_three_registered_in_order(monkeypatch, client):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "s")
    monkeypatch.setenv("FINNHUB_API_KEY", "fnh")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "av")
    get_settings.cache_clear()

    reg = get_default_registry(client)

    assert [type(p).__name__ for p in reg.providers] == [
        "AlpacaProvider",
        "FinnhubProvider",
        "AlphaVantageProvider",
    ]


async def test_empty_when_no_keys(monkeypatch, client):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "")
    monkeypatch.setenv("FINNHUB_API_KEY", "")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "")
    get_settings.cache_clear()

    reg = get_default_registry(client)

    assert reg.providers == []
