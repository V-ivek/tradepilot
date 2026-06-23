from fastapi import APIRouter, Depends, HTTPException

from gateway.deps import get_registry
from gateway.models import CompanyProfile
from gateway.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/profile/{ticker}", response_model=CompanyProfile)
async def get_profile(
    ticker: str, registry: ProviderRegistry = Depends(get_registry)
) -> CompanyProfile:
    data = await registry.get_company_profile(ticker)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No profile for {ticker}")
    return data
