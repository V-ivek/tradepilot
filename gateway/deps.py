"""FastAPI dependency-injection helpers.

A single ``httpx.AsyncClient`` is created at app startup and reused for all
provider calls. The default ``ProviderRegistry`` is built once from settings
and the same instance is returned for every request — providers are stateless
so sharing is safe and avoids the per-request SDK-client construction cost.
Both helpers are overridden in tests via ``app.dependency_overrides``.
"""

import httpx
from fastapi import Depends, HTTPException, Request

from gateway.providers.factory import get_default_registry
from gateway.providers.registry import ProviderRegistry
from gateway.services.paper_trading import PaperTradingService


def get_http_client(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if client is None:
        raise RuntimeError("http_client not initialized on app.state")
    return client


def get_registry(
    request: Request,
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ProviderRegistry:
    registry: ProviderRegistry | None = getattr(request.app.state, "registry", None)
    if registry is None:
        registry = get_default_registry(http_client)
        request.app.state.registry = registry
    return registry


def get_paper_trading(request: Request) -> PaperTradingService:
    adapter: PaperTradingService | None = getattr(request.app.state, "paper_trading", None)
    if adapter is None:
        raise HTTPException(
            status_code=503,
            detail="Paper trading not available — Alpaca keys are not configured.",
        )
    return adapter
