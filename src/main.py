from fastapi import FastAPI

from src.api.routes import health
from src.observability.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="tradepilot", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
