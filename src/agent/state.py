"""LangGraph state shared by every node in the tradepilot graph."""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AssistantState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    user_input: str
    category: str  # "news" | "stock" | "finance" | "fundamentals" | "estimates"
    # | "account" | "trade" | "off_topic"
    active_tickers: list[str]
    pending_trade: dict[str, Any] | None
    awaiting_confirmation: bool
    confirmation_verdict: str  # "AFFIRM" | "DENY" | "MODIFY" | "UNRELATED"
    next_node: str
    blocks: list[dict[str, Any]]
    language: str  # always "en" in v1
