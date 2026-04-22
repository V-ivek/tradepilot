from fastapi import APIRouter, Depends

from gateway.deps import get_registry
from gateway.models import SymbolMatch
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/search", response_model=list[SymbolMatch])
async def search_symbols(
    q: str,
    limit: int = 10,
    registry: ProviderRegistry = Depends(get_registry),
) -> list[SymbolMatch]:
    return await registry.search_symbols(q, limit=limit)
