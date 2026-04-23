"""POST /chat — SSE stream of response blocks.

Loads the user's conversation (creates one if ``conversation_id`` is None),
builds the initial ``AssistantState`` from any persisted ``pending_trade`` /
``awaiting_confirmation``, invokes the graph, and emits:

  event: message_start   data: {conversation_id}
  event: block           data: <block>     (one per block)
  event: message_end     data: {blocks: [...]}
"""

import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from src.agent.graph import build_graph
from src.agent.state import AssistantState
from src.api.middleware.rate_limit import rate_limit_dependency
from src.api.schemas import ChatRequest
from src.services.conversation import ConversationService, Message

logger = logging.getLogger(__name__)
router = APIRouter()


def get_conversation_service(request: Request) -> ConversationService:
    svc: ConversationService | None = getattr(request.app.state, "conversation_service", None)
    if svc is None:
        svc = ConversationService()
        request.app.state.conversation_service = svc
    return svc


def get_graph(request: Request):
    g = getattr(request.app.state, "graph", None)
    if g is None:
        g = build_graph()
        request.app.state.graph = g
    return g


def _sse(event: str, data: Any) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, default=str)}


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    user: dict = Depends(rate_limit_dependency),
    svc: ConversationService = Depends(get_conversation_service),
):
    conv = (
        svc.get_conversation(body.conversation_id)
        if body.conversation_id
        else svc.create_conversation(user_id=user["user_id"])
    )
    if conv is None:
        conv = svc.create_conversation(user_id=user["user_id"])
    if conv.user_id != user["user_id"]:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation.")

    svc.append_message(conv.id, Message(role="user", content=body.user_input))

    graph = get_graph(request)
    state = _initial_state(user_id=user["user_id"], conv_id=conv.id, body=body, svc=svc)

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        yield _sse("message_start", {"conversation_id": conv.id})
        try:
            result = await graph.ainvoke(state)
        except Exception as e:
            logger.exception("chat graph invocation failed")
            yield _sse(
                "error", {"message": "Sorry — something went wrong processing that message."}
            )
            yield _sse("message_end", {"blocks": [], "error": str(e)})
            return

        blocks = result.get("blocks") or []
        for block in blocks:
            yield _sse("block", block)

        svc.append_message(
            conv.id,
            Message(role="assistant", content=_summarize(blocks), blocks=blocks),
        )
        # Persist pending_trade / awaiting_confirmation back to the conversation
        # for the next turn. Stored on the state object as a dict since the
        # in-memory ConversationService doesn't otherwise know about them.
        svc._store[conv.id].__dict__.setdefault("graph_state", {})
        svc._store[conv.id].__dict__["graph_state"] = {
            "pending_trade": result.get("pending_trade"),
            "awaiting_confirmation": bool(result.get("awaiting_confirmation")),
            "active_tickers": result.get("active_tickers") or [],
        }

        yield _sse("message_end", {"blocks": blocks})

    return EventSourceResponse(event_stream())


def _initial_state(
    *,
    user_id: str,
    conv_id: str,
    body: ChatRequest,
    svc: ConversationService,
) -> AssistantState:
    conv = svc.get_conversation(conv_id)
    prior = conv.__dict__.get("graph_state", {}) if conv is not None else {}
    return {
        "user_id": user_id,
        "conversation_id": conv_id,
        "user_input": body.user_input,
        "active_tickers": list(prior.get("active_tickers") or []),
        "pending_trade": prior.get("pending_trade"),
        "awaiting_confirmation": bool(prior.get("awaiting_confirmation")),
        "blocks": [],
        "language": "en",
    }


def _summarize(blocks: list[dict]) -> str:
    for b in blocks:
        if b.get("type") == "text":
            return b.get("content", "")
    return ""
