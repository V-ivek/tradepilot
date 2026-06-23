from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client
from src.tools.fundamentals._common import fetch


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    return await fetch(gateway, ticker, statement="ratios")


@tool
async def get_ratios(ticker: str) -> dict:
    """Key fundamental ratios (PE, PB, ROE, margins)."""
    return await _impl(get_gateway_client(), ticker)
