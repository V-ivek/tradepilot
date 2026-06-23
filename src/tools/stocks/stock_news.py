from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, ticker: str, limit: int = 10) -> list[dict]:
    articles = await gateway.get_news(tickers=[ticker], limit=limit)
    return [a.model_dump(mode="json") for a in articles]


@tool
async def get_stock_news(ticker: str, limit: int = 10) -> list[dict]:
    """Recent news articles for a specific ticker."""
    return await _impl(get_gateway_client(), ticker, limit)
