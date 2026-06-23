from abc import ABC, abstractmethod

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


class DataProvider(ABC):
    """Port for market-data providers.

    Adapters return ``None`` / ``[]`` for unsupported operations; the
    ``ProviderRegistry`` falls through to the next provider.
    """

    @abstractmethod
    async def get_quote(self, ticker: str) -> QuoteData | None: ...

    @abstractmethod
    async def get_company_profile(self, ticker: str) -> CompanyProfile | None: ...

    @abstractmethod
    async def get_fundamentals(
        self, ticker: str, *, statement: str = "all", period: str = "annual"
    ) -> Fundamentals | None: ...

    @abstractmethod
    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]: ...

    @abstractmethod
    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]: ...

    @abstractmethod
    async def get_news(
        self, *, query: str | None = None, tickers: list[str] | None = None, limit: int = 20
    ) -> list[NewsArticle]: ...

    @abstractmethod
    async def get_estimates(self, ticker: str) -> Estimates | None: ...

    @abstractmethod
    async def get_analyst_data(self, ticker: str) -> AnalystData | None: ...
