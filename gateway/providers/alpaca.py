"""Alpaca market-data provider.

Wraps the synchronous ``alpaca-py`` clients; blocking calls are pushed to a
thread via ``asyncio.to_thread`` so this adapter keeps the async interface.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from alpaca.data.enums import DataFeed
from alpaca.data.historical.news import NewsClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest, StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.trading.requests import GetAssetsRequest

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

PERIOD_MAP: dict[str, tuple[TimeFrame, timedelta]] = {
    "1D": (TimeFrame(5, TimeFrameUnit.Minute), timedelta(days=1)),
    "1W": (TimeFrame(1, TimeFrameUnit.Hour), timedelta(days=7)),
    "1M": (TimeFrame.Day, timedelta(days=31)),
    "3M": (TimeFrame.Day, timedelta(days=93)),
    "6M": (TimeFrame.Day, timedelta(days=186)),
    "1Y": (TimeFrame.Day, timedelta(days=366)),
}


class AlpacaProvider(DataProvider):
    def __init__(
        self,
        *,
        key_id: str,
        secret: str,
        stock_client: StockHistoricalDataClient | None = None,
        news_client: NewsClient | None = None,
        trading_client: TradingClient | None = None,
    ):
        self._stock = stock_client or StockHistoricalDataClient(api_key=key_id, secret_key=secret)
        self._news = news_client or NewsClient(api_key=key_id, secret_key=secret)
        self._trading = trading_client or TradingClient(
            api_key=key_id, secret_key=secret, paper=True
        )

    async def get_quote(self, ticker: str) -> QuoteData | None:
        """Build a complete quote from Alpaca's snapshot (IEX feed).

        Uses the latest *trade* price — the bid/ask mid is unreliable on the
        free IEX feed off-hours (one side is often 0). Change/%/OHLC come from
        the daily and previous-daily bars in the same snapshot call.
        """
        ticker = ticker.upper()
        try:
            req = StockSnapshotRequest(symbol_or_symbols=ticker, feed=DataFeed.IEX)
            result = await asyncio.to_thread(self._stock.get_stock_snapshot, req)
        except Exception as e:
            logger.error("AlpacaProvider.get_quote(%s) failed: %s", ticker, e)
            return None

        snap = result.get(ticker) if isinstance(result, dict) else None
        if snap is None:
            return None

        def _pos(value) -> Decimal | None:
            """Return Decimal(value) only if it is a positive number."""
            if value is None:
                return None
            try:
                d = Decimal(str(value))
            except Exception:
                return None
            return d if d > 0 else None

        latest_trade = getattr(snap, "latest_trade", None)
        daily_bar = getattr(snap, "daily_bar", None)
        prev_bar = getattr(snap, "previous_daily_bar", None)

        price = _pos(getattr(latest_trade, "price", None))
        if price is None and daily_bar is not None:
            price = _pos(getattr(daily_bar, "close", None))
        if price is None:
            return None

        prev_close = _pos(getattr(prev_bar, "close", None))
        change = change_pct = None
        if prev_close is not None:
            cents = Decimal("0.01")
            change = (price - prev_close).quantize(cents)
            change_pct = ((price - prev_close) / prev_close * Decimal(100)).quantize(cents)

        ts = getattr(latest_trade, "timestamp", None)
        return QuoteData(
            ticker=ticker,
            price=price,
            change=change,
            change_pct=change_pct,
            high=_pos(getattr(daily_bar, "high", None)),
            low=_pos(getattr(daily_bar, "low", None)),
            open=_pos(getattr(daily_bar, "open", None)),
            previous_close=prev_close,
            volume=int(getattr(daily_bar, "volume", 0) or 0) or None,
            timestamp=ts,
        )

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        ticker = ticker.upper()
        timeframe, span = PERIOD_MAP.get(period.upper(), PERIOD_MAP["1M"])
        end = datetime.now(timezone.utc)
        start = end - span
        try:
            req = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=timeframe,
                start=start,
                end=end,
                feed=DataFeed.IEX,  # free plan has no SIP access; SIP returns empty
            )
            result = await asyncio.to_thread(self._stock.get_stock_bars, req)
        except Exception as e:
            logger.error("AlpacaProvider.get_price_history(%s, %s) failed: %s", ticker, period, e)
            return []

        bars_by_symbol = getattr(result, "data", None) or (
            result if isinstance(result, dict) else {}
        )
        raw_bars = bars_by_symbol.get(ticker, []) if isinstance(bars_by_symbol, dict) else []
        out: list[PriceBar] = []
        for bar in raw_bars:
            try:
                out.append(
                    PriceBar(
                        timestamp=bar.timestamp,
                        open=Decimal(str(bar.open)),
                        high=Decimal(str(bar.high)),
                        low=Decimal(str(bar.low)),
                        close=Decimal(str(bar.close)),
                        volume=int(bar.volume),
                    )
                )
            except Exception as e:
                logger.warning("skipping malformed bar for %s: %s", ticker, e)
        return out

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        try:
            req = NewsRequest(symbols=",".join(tickers) if tickers else None, limit=limit)
            result = await asyncio.to_thread(self._news.get_news, req)
        except Exception as e:
            logger.error("AlpacaProvider.get_news failed: %s", e)
            return []

        articles = getattr(result, "data", None)
        if articles is None and isinstance(result, dict):
            articles = result.get("news", [])
        articles = articles or []

        out: list[NewsArticle] = []
        for a in articles:
            try:
                out.append(
                    NewsArticle(
                        title=a.headline,
                        summary=getattr(a, "summary", None),
                        url=a.url,
                        source=getattr(a, "source", "alpaca"),
                        published_at=a.created_at,
                        tickers=list(getattr(a, "symbols", []) or []),
                    )
                )
            except Exception as e:
                logger.warning("skipping malformed news article: %s", e)
        if query:
            needle = query.lower()
            out = [
                n for n in out if needle in n.title.lower() or needle in (n.summary or "").lower()
            ]
        return out[:limit]

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        needle = query.strip().upper()
        if not needle:
            return []
        try:
            req = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
            assets = await asyncio.to_thread(self._trading.get_all_assets, req)
        except Exception as e:
            logger.error("AlpacaProvider.search_symbols failed: %s", e)
            return []

        out: list[SymbolMatch] = []
        for a in assets or []:
            sym = getattr(a, "symbol", "") or ""
            name = getattr(a, "name", "") or ""
            if needle in sym.upper() or needle in name.upper():
                out.append(
                    SymbolMatch(
                        ticker=sym,
                        name=name,
                        exchange=getattr(a, "exchange", None) and str(a.exchange),
                        type="equity",
                    )
                )
                if len(out) >= limit:
                    break
        return out

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        ticker = ticker.upper()
        try:
            asset = await asyncio.to_thread(self._trading.get_asset, ticker)
        except Exception as e:
            logger.error("AlpacaProvider.get_company_profile(%s) failed: %s", ticker, e)
            return None
        if not asset:
            return None
        return CompanyProfile(
            ticker=getattr(asset, "symbol", ticker),
            name=getattr(asset, "name", "") or "",
            exchange=str(asset.exchange) if getattr(asset, "exchange", None) else None,
        )

    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None:
        return None

    async def get_estimates(self, ticker: str) -> Estimates | None:
        return None

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        return None
