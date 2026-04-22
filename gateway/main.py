from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

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
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    try:
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
    return app


app = create_app()
