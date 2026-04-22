"""HTTP client that fronts the gateway service.

The app never hits Alpaca / Finnhub / Alpha Vantage directly — every external
request goes through the gateway, so one retry + one timeout policy lives here
and the agents stay provider-agnostic.
"""

import logging
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
from gateway.services.paper_trading import (
    Account,
    OrderRequest,
    OrderResult,
    OrderStatus,
    PortfolioHistory,
    Position,
)
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class GatewayClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ):
        self._base_url = (base_url or get_settings().gateway_url).rstrip("/")
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._timeout = timeout

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "GatewayClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> httpx.Response | None:
        url = f"{self._base_url}{path}"
        for attempt in (1, 2):
            try:
                resp = await self._client.request(
                    method, url, params=params, json=json, timeout=self._timeout
                )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning("gateway %s %s attempt %d failed: %s", method, path, attempt, e)
                if attempt == 2:
                    return None
                continue
            if 500 <= resp.status_code < 600 and attempt == 1:
                logger.warning(
                    "gateway %s %s returned %d, retrying", method, path, resp.status_code
                )
                continue
            return resp
        return None

    async def _get_model(self, path: str, model_cls, *, params=None):
        resp = await self._request("GET", path, params=params)
        if resp is None or resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            logger.warning("gateway GET %s returned %d", path, resp.status_code)
            return None
        return model_cls.model_validate(resp.json())

    async def _get_list(self, path: str, model_cls, *, params=None):
        resp = await self._request("GET", path, params=params)
        if resp is None or resp.status_code >= 400:
            return []
        return [model_cls.model_validate(item) for item in resp.json()]

    # ---- market data --------------------------------------------------

    async def get_quote(self, ticker: str) -> QuoteData | None:
        return await self._get_model(f"/quote/{ticker.upper()}", QuoteData)

    async def search_symbols(self, query: str, *, limit: int = 10) -> list[SymbolMatch]:
        return await self._get_list("/search", SymbolMatch, params={"q": query, "limit": limit})

    async def get_news(
        self,
        *,
        query: str | None = None,
        tickers: list[str] | None = None,
        limit: int = 20,
    ) -> list[NewsArticle]:
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        if tickers:
            params["tickers"] = tickers
        return await self._get_list("/news", NewsArticle, params=params)

    async def get_price_history(self, ticker: str, *, period: str = "1M") -> list[PriceBar]:
        return await self._get_list(
            f"/price-history/{ticker.upper()}", PriceBar, params={"period": period}
        )

    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        return await self._get_model(f"/profile/{ticker.upper()}", CompanyProfile)

    async def get_fundamentals(
        self,
        ticker: str,
        *,
        statement: str = "all",
        period: str = "annual",
        count: int = 4,
    ) -> Fundamentals | None:
        return await self._get_model(
            f"/fundamentals/{ticker.upper()}",
            Fundamentals,
            params={"statement": statement, "period": period, "count": count},
        )

    async def get_estimates(self, ticker: str) -> Estimates | None:
        return await self._get_model(f"/estimates/{ticker.upper()}", Estimates)

    async def get_analyst_data(self, ticker: str) -> AnalystData | None:
        return await self._get_model(f"/analyst/{ticker.upper()}", AnalystData)

    # ---- trading ------------------------------------------------------

    async def get_account(self) -> Account | None:
        return await self._get_model("/account", Account)

    async def list_positions(self) -> list[Position]:
        return await self._get_list("/positions", Position)

    async def list_orders(self, status: OrderStatus | None = None) -> list[OrderResult]:
        params = {"status": status} if status else None
        return await self._get_list("/orders", OrderResult, params=params)

    async def place_order(self, req: OrderRequest) -> OrderResult | None:
        resp = await self._request("POST", "/orders", json=req.model_dump(mode="json"))
        if resp is None or resp.status_code >= 400:
            if resp is not None:
                logger.warning("gateway POST /orders returned %d: %s", resp.status_code, resp.text)
            return None
        return OrderResult.model_validate(resp.json())

    async def cancel_order(self, order_id: str) -> bool:
        resp = await self._request("DELETE", f"/orders/{order_id}")
        return resp is not None and resp.status_code in (200, 204)

    async def get_portfolio_history(self, period: str = "1M") -> PortfolioHistory | None:
        return await self._get_model(
            "/portfolio/history", PortfolioHistory, params={"period": period}
        )

    async def health(self) -> dict | None:
        resp = await self._request("GET", "/health")
        if resp is None or resp.status_code >= 400:
            return None
        return resp.json()


_default_client: GatewayClient | None = None


def get_gateway_client() -> GatewayClient:
    """Module-level singleton used by tool `_impl`s when no client is passed."""
    global _default_client
    if _default_client is None:
        _default_client = GatewayClient()
    return _default_client


def set_gateway_client(client: GatewayClient | None) -> None:
    """Override the singleton — used by tests and by app startup."""
    global _default_client
    _default_client = client
