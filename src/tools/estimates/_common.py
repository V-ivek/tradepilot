from src.services.gateway import GatewayClient


async def fetch_estimates(gateway: GatewayClient, ticker: str) -> dict:
    data = await gateway.get_estimates(ticker)
    return data.model_dump(mode="json") if data else {}
