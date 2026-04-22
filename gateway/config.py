from functools import lru_cache

from pydantic_settings import BaseSettings


class GatewaySettings(BaseSettings):
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""
    alpaca_paper_only: bool = True
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
