"""Finnhub market-data provider (fallback for fundamentals, estimates, news).

Uses httpx; the client is injected so tests can mock responses via respx.
"""

import logging
from datetime import datetime, timedelta, timezone
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

BASE_URL = "https://finnhub.io/api/v1"

_PERIOD_TO_DAYS = {
    "1D": 1,
    "1W": 7,
    "1M": 31,
    "3M": 93,
    "6M": 186,
    "1Y": 366,
}


class FinnhubProvider(DataProvider):
    def __init__(self, *, api_key: str, client: httpx.AsyncClient):
        self._api_key = api_key
        self._client = client

    async def _get(self, path: str, params: dict[str, Any]) -> dict | list | None:
        params = {**params, "token": self._api_key}
        try:
            resp = await self._client.get(f"{BASE_URL}{path}", params=params, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Finnhub GET %s failed: %s", path, e)
            return None

    async def get_quote(self, ticker: str) -> QuoteData | None:
        data = await self._get("/quote", {"symbol": ticker.upper()})
        if not isinstance(data, dict) or not data.get("c"):
            return None
        return QuoteData(
            ticker=ticker.upper(),
            price=Decimal(str(data["c"])),
            change=Decimal(str(data["d"])) if data.get("d") is not None else None,
            change_pct=Decimal(str(data["dp"])) if data.get("dp") is not None else None,
            high=Decimal(str(data["h"])) if data.get("h") is not None else None,
            low=Decimal(str(data["l"])) if data.get("l") is not None else None,
            open=Decimal(str(data["o"])) if data.get("o") is not None else None,
            previous_close=Decimal(str(data["pc"])) if data.get("pc") is not None else None,
            timestamp=datetime.fromtimestamp(data["t"], tz=timezone.utc) if data.get("t") else None,
        )

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        data = await self._get("/stock/profile2", {"symbol": ticker.upper()})
        if not isinstance(data, dict) or not data:
            return None
        return CompanyProfile(
            ticker=data.get("ticker", ticker.upper()),
            name=data.get("name", ""),
            exchange=data.get("exchange"),
            industry=data.get("finnhubIndustry"),
            country=data.get("country"),
            currency=data.get("currency"),
            website=data.get("weburl"),
            market_cap=Decimal(str(data["marketCapitalization"]))
            if data.get("marketCapitalization")
            else None,
            logo_url=data.get("logo"),
        )

    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None:
        data = await self._get("/stock/metric", {"symbol": ticker.upper(), "metric": "all"})
        if not isinstance(data, dict) or not data.get("metric"):
            return None
        metric = data["metric"]
        cleaned: dict[str, Decimal | None] = {}
        for k, v in metric.items():
            if isinstance(v, (int, float)):
                cleaned[k] = Decimal(str(v))
            else:
                cleaned[k] = None
        return Fundamentals(ticker=ticker.upper(), period=period, metrics=cleaned)

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        days = _PERIOD_TO_DAYS.get(period.upper(), 31)
        to_ts = int(datetime.now(timezone.utc).timestamp())
        from_ts = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        data = await self._get(
            "/stock/candle",
            {"symbol": ticker.upper(), "resolution": "D", "from": from_ts, "to": to_ts},
        )
        if not isinstance(data, dict) or data.get("s") != "ok":
            return []
        bars: list[PriceBar] = []
        times = data.get("t") or []
        for i, t in enumerate(times):
            try:
                bars.append(
                    PriceBar(
                        timestamp=datetime.fromtimestamp(t, tz=timezone.utc),
                        open=Decimal(str(data["o"][i])),
                        high=Decimal(str(data["h"][i])),
                        low=Decimal(str(data["l"][i])),
                        close=Decimal(str(data["c"][i])),
                        volume=int(data["v"][i]),
                    )
                )
            except Exception as e:
                logger.warning("skipping malformed candle: %s", e)
        return bars

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        # Alpha Vantage's SYMBOL_SEARCH is stronger; keep Finnhub out of symbol search.
        return []

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        if not tickers:
            return []
        out: list[NewsArticle] = []
        today = datetime.now(timezone.utc).date().isoformat()
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        for ticker in tickers:
            data = await self._get(
                "/company-news",
                {"symbol": ticker.upper(), "from": week_ago, "to": today},
            )
            if not isinstance(data, list):
                continue
            for a in data:
                try:
                    out.append(
                        NewsArticle(
                            title=a.get("headline", ""),
                            summary=a.get("summary"),
                            url=a.get("url", ""),
                            source=a.get("source", "finnhub"),
                            published_at=datetime.fromtimestamp(a["datetime"], tz=timezone.utc),
                            tickers=[ticker.upper()],
                        )
                    )
                except Exception as e:
                    logger.warning("skipping malformed finnhub news: %s", e)
        if query:
            needle = query.lower()
            out = [
                n for n in out if needle in n.title.lower() or needle in (n.summary or "").lower()
            ]
        return out[:limit]

    async def get_estimates(self, ticker: str) -> Estimates | None:
        rec_data = await self._get("/stock/recommendation", {"symbol": ticker.upper()})
        target_data = await self._get("/stock/price-target", {"symbol": ticker.upper()})
        if not rec_data and not target_data:
            return None
        latest_rec = rec_data[0] if isinstance(rec_data, list) and rec_data else {}
        recs = {}
        for key in ("strongBuy", "buy", "hold", "sell", "strongSell"):
            if key in latest_rec:
                recs[key] = int(latest_rec[key])
        target = target_data if isinstance(target_data, dict) else {}
        return Estimates(
            ticker=ticker.upper(),
            recommendations=recs,
            price_target_mean=Decimal(str(target["targetMean"]))
            if target.get("targetMean")
            else None,
            price_target_high=Decimal(str(target["targetHigh"]))
            if target.get("targetHigh")
            else None,
            price_target_low=Decimal(str(target["targetLow"])) if target.get("targetLow") else None,
            analyst_count=int(target["numberOfAnalysts"])
            if target.get("numberOfAnalysts")
            else None,
        )

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        data = await self._get("/stock/recommendation", {"symbol": ticker.upper()})
        if not isinstance(data, list) or not data:
            return None
        latest = data[0]
        return AnalystData(
            ticker=ticker.upper(),
            buy=int(latest.get("buy", 0)),
            hold=int(latest.get("hold", 0)),
            sell=int(latest.get("sell", 0)),
            strong_buy=int(latest.get("strongBuy", 0)),
            strong_sell=int(latest.get("strongSell", 0)),
            period=latest.get("period"),
        )
