from fastapi import APIRouter, Depends, HTTPException

from gateway.deps import get_registry
from gateway.models import AnalystData
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/analyst/{ticker}", response_model=AnalystData)
async def get_analyst(
    ticker: str, registry: ProviderRegistry = Depends(get_registry)
) -> AnalystData:
    data = await registry.get_analyst_data(ticker)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No analyst data for {ticker}")
    return data
