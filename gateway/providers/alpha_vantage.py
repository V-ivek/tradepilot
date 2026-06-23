"""Alpha Vantage provider: symbol search + daily price history only.

Alpha Vantage free-tier is rate-limited; this provider intentionally implements
only what it does best. Everything else returns ``None`` / ``[]`` so the
registry falls through.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

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

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageProvider(DataProvider):
    def __init__(self, *, api_key: str, client: httpx.AsyncClient):
        self._api_key = api_key
        self._client = client

    async def _get(self, params: dict[str, Any]) -> dict | None:
        params = {**params, "apikey": self._api_key}
        try:
            resp = await self._client.get(BASE_URL, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and ("Note" in data or "Information" in data):
                # rate-limited; treat as no-data
                return None
            return data if isinstance(data, dict) else None
        except httpx.HTTPError as e:
            logger.error("AlphaVantage GET %s failed: %s", params.get("function"), e)
            return None

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        data = await self._get({"function": "SYMBOL_SEARCH", "keywords": query})
        if not data:
            return []
        matches = data.get("bestMatches") or []
        out: list[SymbolMatch] = []
        for m in matches[:limit]:
            out.append(
                SymbolMatch(
                    ticker=m.get("1. symbol", ""),
                    name=m.get("2. name", ""),
                    exchange=m.get("4. region"),
                    type=m.get("3. type"),
                )
            )
        return out

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        data = await self._get(
            {"function": "TIME_SERIES_DAILY", "symbol": ticker.upper(), "outputsize": "compact"}
        )
        if not data:
            return []
        series = data.get("Time Series (Daily)") or {}
        bars: list[PriceBar] = []
        for date_str, row in series.items():
            try:
                bars.append(
                    PriceBar(
                        timestamp=datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc),
                        open=Decimal(row["1. open"]),
                        high=Decimal(row["2. high"]),
                        low=Decimal(row["3. low"]),
                        close=Decimal(row["4. close"]),
                        volume=int(row["5. volume"]),
                    )
                )
            except Exception as e:
                logger.warning("skipping malformed AV bar for %s: %s", ticker, e)
        bars.sort(key=lambda b: b.timestamp)
        return bars

    async def get_quote(self, ticker: str) -> QuoteData | None:
        return None

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        return None

    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None:
        return None

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        return []

    async def get_estimates(self, ticker: str) -> Estimates | None:
        return None

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        return None
