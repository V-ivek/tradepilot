from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, limit: int = 10) -> list[dict]:
    # No dedicated trending endpoint; fall back to the latest broad-market feed.
    articles = await gateway.get_news(limit=limit)
    return [a.model_dump(mode="json") for a in articles]


@tool
async def get_trending_news(limit: int = 10) -> list[dict]:
    """Latest broadly-trending market news."""
    return await _impl(get_gateway_client(), limit)
