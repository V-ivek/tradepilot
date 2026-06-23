from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    data = await gateway.get_quote(ticker)
    return data.model_dump(mode="json") if data else {}


@tool
async def lookup_stock(ticker: str) -> dict:
    """Look up the latest quote for a US stock ticker."""
    return await _impl(get_gateway_client(), ticker)
