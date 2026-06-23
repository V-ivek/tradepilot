import httpx

from gateway.config import get_settings
from gateway.providers.alpaca import AlpacaProvider
from gateway.providers.alpha_vantage import AlphaVantageProvider
from gateway.providers.base import DataProvider
from gateway.providers.finnhub import FinnhubProvider
from gateway.providers.registry import ProviderRegistry


def get_default_registry(http_client: httpx.AsyncClient) -> ProviderRegistry:
    settings = get_settings()
    providers: list[DataProvider] = []
    if settings.alpaca_api_key_id and settings.alpaca_api_secret_key:
        providers.append(
            AlpacaProvider(
                key_id=settings.alpaca_api_key_id,
                secret=settings.alpaca_api_secret_key,
            )
        )
    if settings.finnhub_api_key:
        providers.append(FinnhubProvider(api_key=settings.finnhub_api_key, client=http_client))
    if settings.alpha_vantage_api_key:
        providers.append(
            AlphaVantageProvider(api_key=settings.alpha_vantage_api_key, client=http_client)
        )
    return ProviderRegistry(providers)
