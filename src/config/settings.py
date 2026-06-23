from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from env vars."""

    litellm_base_url: str
    litellm_api_key: str = "sk-litellm-dev"
    guard_model: str = "claude-haiku-4-5"
    agent_model: str = "claude-sonnet-4-5"
    database_url: str
    redis_url: str
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""
    alpaca_paper_only: bool = True
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    gateway_url: str = "http://gateway:8000"
    rate_limit_per_minute: int = 30
    max_message_length: int = 2000
    semantic_cache_enabled: bool = True
    semantic_cache_finance_ttl: int = 3600
    semantic_cache_stock_ttl: int = 300
    semantic_cache_fundamentals_ttl: int = 1800
    semantic_cache_estimates_ttl: int = 900

    @field_validator("alpaca_paper_only")
    @classmethod
    def _must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("ALPACA_PAPER_ONLY must be true; tradepilot is paper-only.")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
