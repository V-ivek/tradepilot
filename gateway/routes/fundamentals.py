from fastapi import APIRouter, Depends, HTTPException

from gateway.deps import get_registry
from gateway.models import Fundamentals
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/fundamentals/{ticker}", response_model=Fundamentals)
async def get_fundamentals(
    ticker: str,
    statement: str = "all",
    period: str = "annual",
    count: int = 4,
    registry: ProviderRegistry = Depends(get_registry),
) -> Fundamentals:
    data = await registry.get_fundamentals(ticker, statement=statement, period=period)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No fundamentals for {ticker}")
    return data
