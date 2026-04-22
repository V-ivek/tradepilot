from fastapi import APIRouter, Depends

from gateway.deps import get_registry
from gateway.models import PriceBar
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/price-history/{ticker}", response_model=list[PriceBar])
async def get_price_history(
    ticker: str,
    period: str = "1M",
    registry: ProviderRegistry = Depends(get_registry),
) -> list[PriceBar]:
    return await registry.get_price_history(ticker, period=period)
