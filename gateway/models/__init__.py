from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class QuoteData(BaseModel):
    ticker: str
    price: Decimal
    change: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    open: Decimal | None = None
    previous_close: Decimal | None = None
    timestamp: datetime | None = None


class CompanyProfile(BaseModel):
    ticker: str
    name: str
    exchange: str | None = None
    industry: str | None = None
    sector: str | None = None
    country: str | None = None
    currency: str | None = None
    website: str | None = None
    description: str | None = None
    market_cap: Decimal | None = None
    logo_url: str | None = None


class Fundamentals(BaseModel):
    ticker: str
    period: str
    metrics: dict[str, Decimal | None] = {}
    statements: dict[str, dict] = {}


class PriceBar(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class SymbolMatch(BaseModel):
    ticker: str
    name: str
    exchange: str | None = None
    type: str | None = None


class NewsArticle(BaseModel):
    title: str
    summary: str | None = None
    url: str
    source: str
    published_at: datetime
    tickers: list[str] = []


class Estimates(BaseModel):
    ticker: str
    period: str | None = None
    eps_estimate: Decimal | None = None
    revenue_estimate: Decimal | None = None
    recommendations: dict[str, int] = {}
    price_target_mean: Decimal | None = None
    price_target_high: Decimal | None = None
    price_target_low: Decimal | None = None
    analyst_count: int | None = None


class AnalystData(BaseModel):
    ticker: str
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_buy: int = 0
    strong_sell: int = 0
    period: str | None = None
