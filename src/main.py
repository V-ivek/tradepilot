from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.agent.graph import build_graph, default_checkpointer
from src.api.routes import chat, conversations, health
from src.config.settings import get_settings
from src.observability.logging import configure_logging
from src.services.conversation import ConversationService


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    app.state.conversation_service = ConversationService()
    app.state.graph = build_graph(checkpointer=default_checkpointer(settings.database_url))
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="tradepilot", version="0.1.0", lifespan=_lifespan)
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    return app


app = create_app()
