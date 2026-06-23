"""Conversation listing / inspection / deletion. All routes are auth-gated."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.middleware.auth import get_current_user
from src.api.routes.chat import get_conversation_service
from src.api.schemas import ConversationSummary
from src.services.conversation import ConversationService

router = APIRouter()


def _to_summary(conv) -> ConversationSummary:
    return ConversationSummary(
        id=conv.id,
        user_id=conv.user_id,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=len(conv.messages),
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: dict = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
) -> list[ConversationSummary]:
    return [_to_summary(c) for c in svc.list_conversations_for_user(user["user_id"])]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
) -> dict:
    conv = svc.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if conv.user_id != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return conv.model_dump(mode="json")


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
) -> None:
    conv = svc.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if conv.user_id != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    svc.delete(conversation_id)
