"""Request/response schemas for the HTTP layer."""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


class SSEEvent(BaseModel):
    event: str
    data: dict[str, Any]


class ConversationSummary(BaseModel):
    id: str
    user_id: str
    created_at: str
    updated_at: str
    message_count: int
