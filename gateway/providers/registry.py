import logging
from typing import Any, TypeVar

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

T = TypeVar("T")


class ProviderRegistry:
    """Iterates providers in order; falls through on None, [], or exception."""

    def __init__(self, providers: list[DataProvider]):
        self._providers = providers

    @property
    def providers(self) -> list[DataProvider]:
        return list(self._providers)

    async def _call_scalar(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> T | None:
        for provider in self._providers:
            try:
                result = await getattr(provider, method_name)(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "provider %s raised on %s: %s",
                    provider.__class__.__name__,
                    method_name,
                    e,
                )
                continue
            if result is not None:
                return result
        return None

    async def _call_list(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        for provider in self._providers:
            try:
                result = await getattr(provider, method_name)(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "provider %s raised on %s: %s",
                    provider.__class__.__name__,
                    method_name,
                    e,
                )
                continue
            if result:
                return result
        return []

    async def get_quote(self, ticker: str) -> QuoteData | None:
        return await self._call_scalar("get_quote", ticker)

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        return await self._call_scalar("get_company_profile", ticker)

    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None:
        return await self._call_scalar(
            "get_fundamentals", ticker, statement=statement, period=period
        )

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        return await self._call_list("get_price_history", ticker, period=period)

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        return await self._call_list("search_symbols", query, limit=limit)

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        return await self._call_list("get_news", query=query, tickers=tickers, limit=limit)

    async def get_estimates(self, ticker: str) -> Estimates | None:
        return await self._call_scalar("get_estimates", ticker)

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        return await self._call_scalar("get_analyst_data", ticker)
