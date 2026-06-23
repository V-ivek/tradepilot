from fastapi import APIRouter, Depends, HTTPException

from gateway.deps import get_registry
from gateway.models import QuoteData
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/quote/{ticker}", response_model=QuoteData)
async def get_quote(ticker: str, registry: ProviderRegistry = Depends(get_registry)) -> QuoteData:
    data = await registry.get_quote(ticker)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No quote for {ticker}")
    return data
