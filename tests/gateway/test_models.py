from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

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


def test_quote_data_required_ticker_price():
    q = QuoteData(ticker="AAPL", price=Decimal("192.50"))
    assert q.ticker == "AAPL"
    assert q.price == Decimal("192.50")
    with pytest.raises(ValidationError):
        QuoteData(price=Decimal("1"))


def test_price_bar_all_fields_required():
    bar = PriceBar(
        timestamp=datetime.now(timezone.utc),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("0.5"),
        close=Decimal("1.5"),
        volume=100,
    )
    assert bar.volume == 100
    with pytest.raises(ValidationError):
        PriceBar(timestamp=datetime.now(timezone.utc), open=Decimal("1"))


def test_symbol_match_required_fields():
    m = SymbolMatch(ticker="TSLA", name="Tesla, Inc.")
    assert m.ticker == "TSLA"
    with pytest.raises(ValidationError):
        SymbolMatch(ticker="X")


def test_news_article_required_fields():
    n = NewsArticle(
        title="t",
        url="https://x",
        source="wire",
        published_at=datetime.now(timezone.utc),
    )
    assert n.tickers == []
    with pytest.raises(ValidationError):
        NewsArticle(title="t")


def test_company_profile_required():
    p = CompanyProfile(ticker="AAPL", name="Apple")
    assert p.ticker == "AAPL"
    with pytest.raises(ValidationError):
        CompanyProfile(ticker="AAPL")


def test_fundamentals_required():
    f = Fundamentals(ticker="AAPL", period="annual")
    assert f.metrics == {}
    with pytest.raises(ValidationError):
        Fundamentals(ticker="AAPL")


def test_estimates_required():
    e = Estimates(ticker="AAPL")
    assert e.recommendations == {}


def test_analyst_data_required():
    a = AnalystData(ticker="AAPL")
    assert a.buy == 0
    assert a.sell == 0
