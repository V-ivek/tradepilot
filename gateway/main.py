import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from gateway.config import get_settings
from gateway.routes import (
    analyst,
    estimates,
    fundamentals,
    health,
    news,
    price_history,
    profile,
    quotes,
    search,
    trading,
)
from gateway.services.paper_trading_alpaca import AlpacaPaperTradingAdapter

logger = logging.getLogger(__name__)


async def _verify_paper_trading(app: FastAPI) -> None:
    """Construct the paper-trading adapter and verify the account is in paper mode.

    Skipped if Alpaca keys are missing (dev mode). If keys are present but the
    adapter cannot be built or the account does not report ``mode="paper"``,
    raises ``RuntimeError`` so uvicorn exits.
    """
    settings = get_settings()
    if not (settings.alpaca_api_key_id and settings.alpaca_api_secret_key):
        logger.warning(
            "Alpaca keys not set — skipping paper-trading verification. "
            "Trading routes will not function until ALPACA_API_KEY_ID and "
            "ALPACA_API_SECRET_KEY are provided."
        )
        return

    try:
        adapter = AlpacaPaperTradingAdapter(
            key_id=settings.alpaca_api_key_id,
            secret=settings.alpaca_api_secret_key,
        )
    except Exception as e:
        logger.error("Failed to construct AlpacaPaperTradingAdapter: %s", e)
        raise

    account = await adapter.get_account()
    if account.mode != "paper":
        raise RuntimeError(
            f"Refusing to start: Alpaca account reported mode={account.mode!r}, expected 'paper'."
        )
    logger.info("Alpaca paper-trading verified: equity=%s cash=%s", account.equity, account.cash)
    app.state.paper_trading = adapter


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    try:
        await _verify_paper_trading(app)
        yield
    finally:
        await app.state.http_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="tradepilot-gateway", version="0.1.0", lifespan=_lifespan)
    app.include_router(quotes.router)
    app.include_router(search.router)
    app.include_router(news.router)
    app.include_router(profile.router)
    app.include_router(price_history.router)
    app.include_router(fundamentals.router)
    app.include_router(estimates.router)
    app.include_router(analyst.router)
    app.include_router(health.router)
    app.include_router(trading.router)
    return app


app = create_app()
