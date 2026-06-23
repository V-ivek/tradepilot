import pytest

from src.agent.nodes.router import route, router_node
from src.agent.state import AssistantState


@pytest.mark.parametrize(
    "category,expected",
    [
        ("news", "news_agent"),
        ("stock", "stock_agent"),
        ("finance", "finance_agent"),
        ("fundamentals", "fundamentals_agent"),
        ("estimates", "estimates_agent"),
        ("account", "account_agent"),
        ("trade", "trade_agent"),
        ("off_topic", "rejection"),
        ("unknown_made_up", "rejection"),
    ],
)
def test_route_maps_category(category, expected):
    state: AssistantState = {"category": category}
    assert route(state) == expected


def test_awaiting_confirmation_forces_classifier():
    state: AssistantState = {
        "category": "stock",
        "awaiting_confirmation": True,
        "pending_trade": {"symbol": "AAPL"},
    }
    assert route(state) == "confirmation_classifier"


def test_awaiting_without_pending_trade_does_not_force_classifier():
    state: AssistantState = {"category": "stock", "awaiting_confirmation": True}
    assert route(state) == "stock_agent"


async def test_router_node_writes_next_node():
    state: AssistantState = {"category": "stock"}
    out = await router_node(state)
    assert out["next_node"] == "stock_agent"
