from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, period: str = "1M") -> dict:
    history = await gateway.get_portfolio_history(period=period)
    return history.model_dump(mode="json") if history else {}


@tool
async def get_portfolio_history(period: str = "1M") -> dict:
    """Paper-trading portfolio equity history. Period: 1D, 1W, 1M, 3M, 6M, 1Y."""
    return await _impl(get_gateway_client(), period)
