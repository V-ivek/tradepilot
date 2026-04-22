from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(
    gateway: GatewayClient,
    query: str | None = None,
    tickers: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    articles = await gateway.get_news(query=query, tickers=tickers, limit=limit)
    return [a.model_dump(mode="json") for a in articles]


@tool
async def search_news(
    query: str | None = None,
    tickers: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search market + company news. Provide a query, a ticker list, or both."""
    return await _impl(get_gateway_client(), query, tickers, limit)
