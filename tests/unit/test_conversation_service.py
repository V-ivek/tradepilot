import pytest

from src.services.conversation import ConversationService, Message


def test_create_and_get_conversation():
    svc = ConversationService()
    conv = svc.create_conversation(user_id="u1")

    fetched = svc.get_conversation(conv.id)
    assert fetched is not None
    assert fetched.user_id == "u1"
    assert fetched.messages == []


def test_append_message_updates_conversation():
    svc = ConversationService()
    conv = svc.create_conversation("u1")

    svc.append_message(conv.id, Message(role="user", content="hi"))

    fetched = svc.get_conversation(conv.id)
    assert len(fetched.messages) == 1
    assert fetched.messages[0].content == "hi"


def test_append_to_unknown_conversation_raises():
    svc = ConversationService()
    with pytest.raises(KeyError):
        svc.append_message("nope", Message(role="user", content="hi"))


def test_list_conversations_by_user():
    svc = ConversationService()
    a1 = svc.create_conversation("u1")
    a2 = svc.create_conversation("u1")
    b = svc.create_conversation("u2")

    u1_convs = svc.list_conversations_for_user("u1")
    u2_convs = svc.list_conversations_for_user("u2")

    assert {c.id for c in u1_convs} == {a1.id, a2.id}
    assert {c.id for c in u2_convs} == {b.id}


def test_delete_conversation():
    svc = ConversationService()
    conv = svc.create_conversation("u1")

    svc.delete(conv.id)

    assert svc.get_conversation(conv.id) is None


def test_updated_at_advances_on_append():
    svc = ConversationService()
    conv = svc.create_conversation("u1")
    first = conv.updated_at

    svc.append_message(conv.id, Message(role="user", content="hi"))

    assert svc.get_conversation(conv.id).updated_at >= first
