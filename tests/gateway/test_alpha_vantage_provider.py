from decimal import Decimal

import httpx
import pytest
import respx

from gateway.providers.alpha_vantage import AlphaVantageProvider


@pytest.fixture
async def provider():
    async with httpx.AsyncClient() as client:
        yield AlphaVantageProvider(api_key="k", client=client)


@respx.mock
async def test_search_symbols_maps_best_matches(provider):
    respx.get("https://www.alphavantage.co/query").respond(
        json={
            "bestMatches": [
                {
                    "1. symbol": "AAPL",
                    "2. name": "Apple Inc",
                    "3. type": "Equity",
                    "4. region": "United States",
                }
            ]
        }
    )

    matches = await provider.search_symbols("apple", limit=5)

    assert len(matches) == 1
    assert matches[0].ticker == "AAPL"
    assert matches[0].type == "Equity"


@respx.mock
async def test_search_symbols_empty_on_rate_limit(provider):
    respx.get("https://www.alphavantage.co/query").respond(
        json={"Note": "API call frequency is limited"}
    )

    assert await provider.search_symbols("AAPL") == []


@respx.mock
async def test_get_price_history_maps_daily_series(provider):
    respx.get("https://www.alphavantage.co/query").respond(
        json={
            "Time Series (Daily)": {
                "2026-04-21": {
                    "1. open": "188.50",
                    "2. high": "190.00",
                    "3. low": "187.50",
                    "4. close": "189.55",
                    "5. volume": "12345678",
                }
            }
        }
    )

    bars = await provider.get_price_history("AAPL", period="1M")

    assert len(bars) == 1
    assert bars[0].close == Decimal("189.55")
    assert bars[0].volume == 12345678


@respx.mock
async def test_get_price_history_empty_on_error(provider):
    respx.get("https://www.alphavantage.co/query").respond(status_code=500)

    assert await provider.get_price_history("AAPL") == []


async def test_unsupported_methods_return_none_or_empty(provider):
    assert await provider.get_quote("AAPL") is None
    assert await provider.get_company_profile("AAPL") is None
    assert await provider.get_fundamentals("AAPL") is None
    assert await provider.get_news() == []
    assert await provider.get_estimates("AAPL") is None
    assert await provider.get_analyst_data("AAPL") is None
