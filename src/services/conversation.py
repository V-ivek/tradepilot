"""In-memory conversation service (MVP).

A Postgres-backed swap is a future refactor; the service API is the seam so
the swap doesn't touch call sites.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["user", "assistant", "system", "tool"]


class Message(BaseModel):
    role: Role
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    blocks: list[dict] | None = None


class Conversation(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[Message] = []


class ConversationService:
    def __init__(self) -> None:
        self._store: dict[str, Conversation] = {}

    def create_conversation(self, user_id: str) -> Conversation:
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self._store[conv.id] = conv
        return conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self._store.get(conversation_id)

    def append_message(self, conversation_id: str, message: Message) -> Conversation:
        conv = self._store.get(conversation_id)
        if conv is None:
            raise KeyError(conversation_id)
        conv.messages.append(message)
        conv.updated_at = datetime.now(timezone.utc)
        return conv

    def list_conversations_for_user(self, user_id: str) -> list[Conversation]:
        return [c for c in self._store.values() if c.user_id == user_id]

    def delete(self, conversation_id: str) -> None:
        self._store.pop(conversation_id, None)
