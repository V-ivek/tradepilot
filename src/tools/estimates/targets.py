from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client
from src.tools.estimates._common import fetch_estimates


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    data = await fetch_estimates(gateway, ticker)
    if not data:
        return {}
    return {
        "ticker": data.get("ticker"),
        "price_target_mean": data.get("price_target_mean"),
        "price_target_high": data.get("price_target_high"),
        "price_target_low": data.get("price_target_low"),
        "analyst_count": data.get("analyst_count"),
    }


@tool
async def get_targets(ticker: str) -> dict:
    """Analyst price target (mean / high / low) and analyst count."""
    return await _impl(get_gateway_client(), ticker)
