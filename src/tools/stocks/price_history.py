from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, ticker: str, period: str = "1M") -> list[dict]:
    bars = await gateway.get_price_history(ticker, period=period)
    return [b.model_dump(mode="json") for b in bars]


@tool
async def get_price_history(ticker: str, period: str = "1M") -> list[dict]:
    """OHLC price history. Period: 1D, 1W, 1M, 3M, 6M, 1Y."""
    return await _impl(get_gateway_client(), ticker, period)
