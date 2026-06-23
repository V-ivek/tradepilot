from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient) -> list[dict]:
    positions = await gateway.list_positions()
    return [p.model_dump(mode="json") for p in positions]


@tool
async def list_positions() -> list[dict]:
    """Paper-trading open positions."""
    return await _impl(get_gateway_client())
