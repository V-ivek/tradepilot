from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client
from src.tools.fundamentals._common import fetch


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    return await fetch(gateway, ticker, statement="filings")


@tool
async def get_filings(ticker: str) -> dict:
    """Recent SEC filings (10-K, 10-Q, 8-K)."""
    return await _impl(get_gateway_client(), ticker)
