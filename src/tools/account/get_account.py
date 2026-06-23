from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient) -> dict:
    account = await gateway.get_account()
    return account.model_dump(mode="json") if account else {}


@tool
async def get_account() -> dict:
    """Paper-trading account summary (equity, cash, buying power)."""
    return await _impl(get_gateway_client())
