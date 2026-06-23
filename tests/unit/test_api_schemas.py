import pytest
from pydantic import ValidationError

from src.api.schemas import ChatRequest, ConversationSummary, SSEEvent


def test_chat_request_requires_user_input():
    with pytest.raises(ValidationError):
        ChatRequest()  # type: ignore[call-arg]


def test_chat_request_rejects_empty_string():
    with pytest.raises(ValidationError):
        ChatRequest(user_input="")


def test_chat_request_rejects_overlong():
    with pytest.raises(ValidationError):
        ChatRequest(user_input="x" * 2001)


def test_chat_request_accepts_optional_conversation_id():
    r = ChatRequest(user_input="hi")
    assert r.conversation_id is None

    r2 = ChatRequest(user_input="hi", conversation_id="abc")
    assert r2.conversation_id == "abc"


def test_sse_event_shape():
    e = SSEEvent(event="block", data={"type": "text", "content": "hi"})
    assert e.event == "block"
    assert e.data["content"] == "hi"


def test_conversation_summary_roundtrip():
    s = ConversationSummary(
        id="c1",
        user_id="u1",
        created_at="2026-04-22T10:00:00Z",
        updated_at="2026-04-22T10:05:00Z",
        message_count=3,
    )
    assert ConversationSummary.model_validate(s.model_dump()) == s
