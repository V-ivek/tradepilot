from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client
from src.tools.estimates._common import fetch_estimates


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    data = await fetch_estimates(gateway, ticker)
    if not data:
        return {}
    return {
        "ticker": data.get("ticker"),
        "recommendations": data.get("recommendations") or {},
    }


@tool
async def get_recommendations(ticker: str) -> dict:
    """Analyst buy/hold/sell + strong-buy/strong-sell counts."""
    return await _impl(get_gateway_client(), ticker)
