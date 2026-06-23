from decimal import Decimal

import httpx
import pytest
import respx

from gateway.providers.finnhub import FinnhubProvider


@pytest.fixture
async def provider():
    async with httpx.AsyncClient() as client:
        yield FinnhubProvider(api_key="k", client=client)


@respx.mock
async def test_get_quote_maps_fields(provider):
    respx.get("https://finnhub.io/api/v1/quote").respond(
        json={
            "c": 189.55,
            "d": 1.23,
            "dp": 0.65,
            "h": 190.00,
            "l": 188.00,
            "o": 188.50,
            "pc": 188.32,
            "t": 1714000000,
        }
    )

    q = await provider.get_quote("aapl")

    assert q is not None
    assert q.ticker == "AAPL"
    assert q.price == Decimal("189.55")
    assert q.previous_close == Decimal("188.32")


@respx.mock
async def test_get_quote_returns_none_on_http_error(provider):
    respx.get("https://finnhub.io/api/v1/quote").respond(status_code=500)

    assert await provider.get_quote("AAPL") is None


@respx.mock
async def test_get_quote_returns_none_when_current_missing(provider):
    respx.get("https://finnhub.io/api/v1/quote").respond(json={"c": 0})

    assert await provider.get_quote("AAPL") is None


@respx.mock
async def test_get_company_profile_maps_fields(provider):
    respx.get("https://finnhub.io/api/v1/stock/profile2").respond(
        json={
            "ticker": "AAPL",
            "name": "Apple Inc",
            "exchange": "NASDAQ",
            "finnhubIndustry": "Technology",
            "country": "US",
            "currency": "USD",
            "weburl": "https://apple.com",
            "marketCapitalization": 3000000,
            "logo": "https://cdn/apple.png",
        }
    )

    p = await provider.get_company_profile("AAPL")

    assert p is not None
    assert p.name == "Apple Inc"
    assert p.industry == "Technology"
    assert p.logo_url == "https://cdn/apple.png"


@respx.mock
async def test_get_fundamentals_maps_metric(provider):
    respx.get("https://finnhub.io/api/v1/stock/metric").respond(
        json={"metric": {"peBasicExtraTTM": 28.5, "name": "Apple"}}
    )

    f = await provider.get_fundamentals("AAPL")

    assert f is not None
    assert f.metrics["peBasicExtraTTM"] == Decimal("28.5")
    assert f.metrics["name"] is None  # strings become None


@respx.mock
async def test_get_price_history_maps_candles(provider):
    respx.get("https://finnhub.io/api/v1/stock/candle").respond(
        json={
            "s": "ok",
            "t": [1713916800],
            "o": [188.50],
            "h": [190.00],
            "l": [187.50],
            "c": [189.55],
            "v": [12345678],
        }
    )

    bars = await provider.get_price_history("AAPL", period="1M")

    assert len(bars) == 1
    assert bars[0].close == Decimal("189.55")


@respx.mock
async def test_get_price_history_empty_on_no_data(provider):
    respx.get("https://finnhub.io/api/v1/stock/candle").respond(json={"s": "no_data"})

    assert await provider.get_price_history("AAPL") == []


@respx.mock
async def test_search_symbols_returns_empty(provider):
    assert await provider.search_symbols("AAPL") == []


@respx.mock
async def test_get_news_maps_company_news(provider):
    respx.get("https://finnhub.io/api/v1/company-news").respond(
        json=[
            {
                "headline": "Apple launches X",
                "summary": "...",
                "url": "https://n/1",
                "source": "wire",
                "datetime": 1714000000,
            }
        ]
    )

    articles = await provider.get_news(tickers=["AAPL"], limit=5)

    assert len(articles) == 1
    assert articles[0].tickers == ["AAPL"]


async def test_get_news_empty_without_tickers(provider):
    assert await provider.get_news(tickers=None) == []


@respx.mock
async def test_get_estimates_combines_recommendation_and_target(provider):
    respx.get("https://finnhub.io/api/v1/stock/recommendation").respond(
        json=[{"strongBuy": 10, "buy": 5, "hold": 3, "sell": 1, "strongSell": 0}]
    )
    respx.get("https://finnhub.io/api/v1/stock/price-target").respond(
        json={"targetMean": 210.0, "targetHigh": 260.0, "targetLow": 180.0, "numberOfAnalysts": 30}
    )

    e = await provider.get_estimates("AAPL")

    assert e is not None
    assert e.price_target_mean == Decimal("210.0")
    assert e.analyst_count == 30
    assert e.recommendations["buy"] == 5


@respx.mock
async def test_get_analyst_data_maps_latest(provider):
    respx.get("https://finnhub.io/api/v1/stock/recommendation").respond(
        json=[
            {
                "buy": 5,
                "hold": 3,
                "sell": 1,
                "strongBuy": 10,
                "strongSell": 0,
                "period": "2026-04-01",
            }
        ]
    )

    a = await provider.get_analyst_data("AAPL")

    assert a is not None
    assert a.buy == 5
    assert a.strong_buy == 10
    assert a.period == "2026-04-01"
