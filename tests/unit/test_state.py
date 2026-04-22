from langchain_core.messages import AIMessage, HumanMessage

from src.agent.state import AssistantState


def test_state_is_total_false_typed_dict():
    s: AssistantState = {}
    s["user_id"] = "u1"
    s["user_input"] = "hi"
    s["blocks"] = []
    s["active_tickers"] = ["AAPL"]
    assert s["user_id"] == "u1"


def test_messages_accept_langchain_message_types():
    s: AssistantState = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
    assert len(s["messages"]) == 2
