from fastapi import APIRouter, Depends, HTTPException

from gateway.deps import get_registry
from gateway.models import Estimates
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/estimates/{ticker}", response_model=Estimates)
async def get_estimates(
    ticker: str, registry: ProviderRegistry = Depends(get_registry)
) -> Estimates:
    data = await registry.get_estimates(ticker)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No estimates for {ticker}")
    return data
