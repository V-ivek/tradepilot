from fastapi import APIRouter, Depends, Query

from gateway.deps import get_registry
from gateway.models import NewsArticle
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/news", response_model=list[NewsArticle])
async def get_news(
    q: str | None = None,
    tickers: list[str] | None = Query(default=None),
    limit: int = 20,
    registry: ProviderRegistry = Depends(get_registry),
) -> list[NewsArticle]:
    return await registry.get_news(query=q, tickers=tickers, limit=limit)
