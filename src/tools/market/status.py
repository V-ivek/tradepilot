from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient) -> dict:
    # The gateway does not yet expose /market/clock. Return a deterministic
    # placeholder so the LLM can still answer "is the market open?" truthfully.
    health = await gateway.health()
    return {
        "known": False,
        "note": "Market open/close status not yet wired up; check a broker or marketplace.",
        "gateway_health": health or {},
    }


@tool
async def get_market_status() -> dict:
    """Check whether US equity markets are currently open. Placeholder in v0.1."""
    return await _impl(get_gateway_client())
