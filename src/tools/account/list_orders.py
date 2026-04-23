from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, status: str | None = None) -> list[dict]:
    orders = await gateway.list_orders(status=status) if status else await gateway.list_orders()
    return [o.model_dump(mode="json") for o in orders]


@tool
async def list_orders(status: str | None = None) -> list[dict]:
    """Paper-trading orders. Optional status: new, filled, canceled, etc."""
    return await _impl(get_gateway_client(), status)
