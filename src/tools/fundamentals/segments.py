from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client
from src.tools.fundamentals._common import fetch


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    return await fetch(gateway, ticker, statement="segments")


@tool
async def get_segments(ticker: str) -> dict:
    """Revenue by business / geographic segment."""
    return await _impl(get_gateway_client(), ticker)
