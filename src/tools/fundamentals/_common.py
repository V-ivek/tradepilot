from src.services.gateway import GatewayClient


async def fetch(
    gateway: GatewayClient,
    ticker: str,
    *,
    statement: str = "all",
    period: str = "annual",
) -> dict:
    data = await gateway.get_fundamentals(ticker, statement=statement, period=period)
    return data.model_dump(mode="json") if data else {}
