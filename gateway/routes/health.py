from fastapi import APIRouter, Depends

from gateway.deps import get_registry
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/health")
async def health(registry: ProviderRegistry = Depends(get_registry)) -> dict:
    return {
        "status": "ok",
        "trading_mode": "paper",
        "providers": [type(p).__name__ for p in registry.providers],
    }
