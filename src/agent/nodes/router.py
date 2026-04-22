"""Router node: deterministic category → next-node mapping.

If ``awaiting_confirmation`` is True, the router always routes to
``confirmation_classifier`` regardless of category — an active pending trade
must be resolved before any new request is processed.
"""

from src.agent.state import AssistantState

_CATEGORY_TO_NODE: dict[str, str] = {
    "news": "news_agent",
    "stock": "stock_agent",
    "finance": "finance_agent",
    "fundamentals": "fundamentals_agent",
    "estimates": "estimates_agent",
    "account": "account_agent",
    "trade": "trade_agent",
    "off_topic": "rejection",
}


def route(state: AssistantState) -> str:
    if state.get("awaiting_confirmation") and state.get("pending_trade"):
        return "confirmation_classifier"
    return _CATEGORY_TO_NODE.get(state.get("category", "off_topic"), "rejection")


async def router_node(state: AssistantState) -> AssistantState:
    state["next_node"] = route(state)
    return state
