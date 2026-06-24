from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from gateway.providers.alpaca import AlpacaProvider


def _make_provider(stock=None, news=None, trading=None):
    return AlpacaProvider(
        key_id="k",
        secret="s",
        stock_client=stock or MagicMock(),
        news_client=news or MagicMock(),
        trading_client=trading or MagicMock(),
    )


def _snapshot(*, trade_price, daily=None, prev_close=None):
    daily = daily or {}
    return SimpleNamespace(
        latest_trade=SimpleNamespace(
            price=trade_price,
            timestamp=datetime(2026, 6, 22, 20, 45, tzinfo=timezone.utc),
        ),
        daily_bar=SimpleNamespace(
            open=daily.get("open"),
            high=daily.get("high"),
            low=daily.get("low"),
            close=daily.get("close"),
            volume=daily.get("volume", 0),
        ),
        previous_daily_bar=SimpleNamespace(close=prev_close),
    )


async def test_get_quote_uses_latest_trade_price_and_computes_change():
    stock = MagicMock()
    stock.get_stock_snapshot.return_value = {
        "AAPL": _snapshot(
            trade_price=296.64,
            daily={"open": 297.41, "high": 302.41, "low": 296.82, "close": 296.85, "volume": 10},
            prev_close=297.86,
        )
    }
    p = _make_provider(stock=stock)

    result = await p.get_quote("aapl")

    assert result is not None
    assert result.ticker == "AAPL"
    assert result.price == Decimal("296.64")  # last trade, NOT a bid/ask mid
    assert result.previous_close == Decimal("297.86")
    assert result.change == Decimal("296.64") - Decimal("297.86")
    assert result.change_pct is not None and result.change_pct < 0


async def test_get_quote_regression_no_half_price_from_zero_ask():
    # The original bug: (bid + 0-ask)/2 produced half the real price. We now use
    # the trade price, so a zero/empty ask in the snapshot is irrelevant.
    stock = MagicMock()
    stock.get_stock_snapshot.return_value = {
        "AAPL": _snapshot(trade_price=282.90, prev_close=283.00)
    }
    p = _make_provider(stock=stock)

    result = await p.get_quote("AAPL")

    assert result is not None
    assert result.price == Decimal("282.90")  # not 141.45


async def test_get_quote_falls_back_to_daily_close_when_no_trade():
    stock = MagicMock()
    stock.get_stock_snapshot.return_value = {
        "AAPL": _snapshot(trade_price=0, daily={"close": 300.0}, prev_close=299.0)
    }
    p = _make_provider(stock=stock)

    result = await p.get_quote("AAPL")

    assert result is not None
    assert result.price == Decimal("300.0")


async def test_get_quote_returns_none_on_exception():
    stock = MagicMock()
    stock.get_stock_snapshot.side_effect = RuntimeError("429")
    p = _make_provider(stock=stock)

    assert await p.get_quote("AAPL") is None


async def test_get_quote_returns_none_when_symbol_missing():
    stock = MagicMock()
    stock.get_stock_snapshot.return_value = {}
    p = _make_provider(stock=stock)

    assert await p.get_quote("AAPL") is None


async def test_get_price_history_maps_bars():
    bar = SimpleNamespace(
        timestamp=datetime(2026, 4, 22, tzinfo=timezone.utc),
        open=100.0,
        high=101.5,
        low=99.5,
        close=100.75,
        volume=12345,
    )
    stock = MagicMock()
    stock.get_stock_bars.return_value = SimpleNamespace(data={"AAPL": [bar]})
    p = _make_provider(stock=stock)

    bars = await p.get_price_history("AAPL", period="1M")

    assert len(bars) == 1
    assert bars[0].close == Decimal("100.75")
    assert bars[0].volume == 12345


async def test_get_price_history_returns_empty_on_exception():
    stock = MagicMock()
    stock.get_stock_bars.side_effect = RuntimeError("500")
    p = _make_provider(stock=stock)

    assert await p.get_price_history("AAPL", period="1M") == []


async def test_get_news_maps_articles():
    article = SimpleNamespace(
        headline="Apple launches something",
        summary="...",
        url="https://news/1",
        source="wire",
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        symbols=["AAPL"],
    )
    news_client = MagicMock()
    news_client.get_news.return_value = SimpleNamespace(data=[article])
    p = _make_provider(news=news_client)

    articles = await p.get_news(tickers=["AAPL"], limit=10)

    assert len(articles) == 1
    assert articles[0].title == "Apple launches something"
    assert articles[0].tickers == ["AAPL"]


async def test_get_news_returns_empty_on_exception():
    news_client = MagicMock()
    news_client.get_news.side_effect = RuntimeError("429")
    p = _make_provider(news=news_client)

    assert await p.get_news(limit=10) == []


async def test_search_symbols_filters_assets():
    assets = [
        SimpleNamespace(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
        SimpleNamespace(symbol="GOOG", name="Alphabet", exchange="NASDAQ"),
        SimpleNamespace(symbol="APPS", name="Digital Turbine", exchange="NASDAQ"),
    ]
    trading = MagicMock()
    trading.get_all_assets.return_value = assets
    p = _make_provider(trading=trading)

    matches = await p.search_symbols("aap", limit=5)

    tickers = [m.ticker for m in matches]
    assert "AAPL" in tickers


async def test_search_symbols_returns_empty_on_exception():
    trading = MagicMock()
    trading.get_all_assets.side_effect = RuntimeError("500")
    p = _make_provider(trading=trading)

    assert await p.search_symbols("AAPL") == []


async def test_get_company_profile_maps_asset():
    asset = SimpleNamespace(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
    trading = MagicMock()
    trading.get_asset.return_value = asset
    p = _make_provider(trading=trading)

    profile = await p.get_company_profile("aapl")

    assert profile is not None
    assert profile.ticker == "AAPL"
    assert profile.name == "Apple Inc."
    assert profile.exchange == "NASDAQ"


async def test_fundamentals_estimates_analyst_return_none():
    p = _make_provider()

    assert await p.get_fundamentals("AAPL") is None
    assert await p.get_estimates("AAPL") is None
    assert await p.get_analyst_data("AAPL") is None
