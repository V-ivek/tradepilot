from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client
from src.tools.estimates._common import fetch_estimates


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    data = await fetch_estimates(gateway, ticker)
    if not data:
        return {}
    return {
        "ticker": data.get("ticker"),
        "eps_estimate": data.get("eps_estimate"),
        "revenue_estimate": data.get("revenue_estimate"),
        "period": data.get("period"),
    }


@tool
async def get_earnings(ticker: str) -> dict:
    """Consensus EPS and revenue estimates for the upcoming period."""
    return await _impl(get_gateway_client(), ticker)
