from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, query: str, limit: int = 10) -> list[dict]:
    matches = await gateway.search_symbols(query, limit=limit)
    return [m.model_dump(mode="json") for m in matches]


@tool
async def search_stock(query: str, limit: int = 10) -> list[dict]:
    """Search US stocks by name or partial ticker."""
    return await _impl(get_gateway_client(), query, limit)
