from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    data = await gateway.get_analyst_data(ticker)
    return data.model_dump(mode="json") if data else {}


@tool
async def get_analyst(ticker: str) -> dict:
    """Analyst recommendation counts (buy/hold/sell, strong buy/sell)."""
    return await _impl(get_gateway_client(), ticker)
