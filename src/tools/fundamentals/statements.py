from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client
from src.tools.fundamentals._common import fetch


async def _impl(gateway: GatewayClient, ticker: str, period: str = "annual") -> dict:
    return await fetch(gateway, ticker, statement="all", period=period)


@tool
async def get_statements(ticker: str, period: str = "annual") -> dict:
    """Income statement, balance sheet, cash flow. period: annual or quarterly."""
    return await _impl(get_gateway_client(), ticker, period)
