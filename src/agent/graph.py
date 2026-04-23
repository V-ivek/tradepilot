"""Assemble the tradepilot LangGraph.

The shape is (edges elided for brevity):

    guard ─┬─ (awaiting_confirmation=True) ──► confirmation_classifier
           └─ (next_node) ──► {news,stock,finance,fundamentals,
                                estimates,account,trade,rejection}_agent

    confirmation_classifier ─┬─ AFFIRM   ──► execute_trade
                             ├─ MODIFY   ──► trade_agent
                             └─ DENY/UNRELATED ──► validator

    trade_agent ──► confirmation_gate ──► validator
    {all other agents, execute_trade, rejection} ──► validator

    validator ──► END

Node implementations can be overridden at build time via the ``nodes`` kwarg —
used by graph-level tests to stub LLM-backed nodes with deterministic fakes.
"""

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from src.agent.nodes.account_agent import account_agent_node
from src.agent.nodes.confirmation import confirmation_gate_node
from src.agent.nodes.confirmation_classifier import confirmation_classifier_node
from src.agent.nodes.estimates_agent import estimates_agent_node
from src.agent.nodes.execute_trade import execute_trade_node
from src.agent.nodes.finance_agent import finance_agent_node
from src.agent.nodes.fundamentals_agent import fundamentals_agent_node
from src.agent.nodes.guard import guard_node
from src.agent.nodes.news_agent import news_agent_node
from src.agent.nodes.rejection import rejection_node
from src.agent.nodes.stock_agent import stock_agent_node
from src.agent.nodes.trade_agent import trade_agent_node
from src.agent.nodes.validator import validator_node
from src.agent.state import AssistantState

AGENT_NODES = (
    "news_agent",
    "stock_agent",
    "finance_agent",
    "fundamentals_agent",
    "estimates_agent",
    "account_agent",
    "trade_agent",
)

DEFAULT_NODES: dict[str, Callable] = {
    "guard": guard_node,
    "rejection": rejection_node,
    "news_agent": news_agent_node,
    "stock_agent": stock_agent_node,
    "finance_agent": finance_agent_node,
    "fundamentals_agent": fundamentals_agent_node,
    "estimates_agent": estimates_agent_node,
    "account_agent": account_agent_node,
    "trade_agent": trade_agent_node,
    "confirmation_classifier": confirmation_classifier_node,
    "confirmation_gate": confirmation_gate_node,
    "execute_trade": execute_trade_node,
    "validator": validator_node,
}


def _route_after_guard(state: AssistantState) -> str:
    if state.get("awaiting_confirmation") and state.get("pending_trade"):
        return "confirmation_classifier"
    nxt = state.get("next_node", "rejection")
    if nxt not in AGENT_NODES and nxt != "rejection":
        return "rejection"
    return nxt


def _route_after_classifier(state: AssistantState) -> str:
    verdict = state.get("confirmation_verdict")
    if verdict == "AFFIRM":
        return "execute_trade"
    if verdict == "MODIFY":
        return "trade_agent"
    return "validator"  # DENY or UNRELATED → clear handled by execute_trade path? no: validator


def build_graph(
    *,
    checkpointer: Any = None,
    nodes: dict[str, Callable] | None = None,
):
    n = {**DEFAULT_NODES, **(nodes or {})}
    g = StateGraph(AssistantState)

    for name, fn in n.items():
        g.add_node(name, fn)

    g.set_entry_point("guard")

    g.add_conditional_edges(
        "guard",
        _route_after_guard,
        {
            "confirmation_classifier": "confirmation_classifier",
            "news_agent": "news_agent",
            "stock_agent": "stock_agent",
            "finance_agent": "finance_agent",
            "fundamentals_agent": "fundamentals_agent",
            "estimates_agent": "estimates_agent",
            "account_agent": "account_agent",
            "trade_agent": "trade_agent",
            "rejection": "rejection",
        },
    )

    g.add_conditional_edges(
        "confirmation_classifier",
        _route_after_classifier,
        {
            "execute_trade": "execute_trade",
            "trade_agent": "trade_agent",
            "validator": "validator",
        },
    )

    # Agents and terminal nodes → validator.
    for node in [
        "news_agent",
        "stock_agent",
        "finance_agent",
        "fundamentals_agent",
        "estimates_agent",
        "account_agent",
        "execute_trade",
        "rejection",
    ]:
        g.add_edge(node, "validator")

    # Trade agent halts the turn at the confirmation gate.
    g.add_edge("trade_agent", "confirmation_gate")
    g.add_edge("confirmation_gate", "validator")

    g.add_edge("validator", END)

    return g.compile(checkpointer=checkpointer)
