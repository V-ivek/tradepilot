"""Confirmation gate — the load-bearing safety node.

Sits downstream of ``trade_agent``. When ``awaiting_confirmation`` is set AND
there is a ``pending_trade``, the node is a no-op: state carries forward,
the graph edge continues to the validator and END, and LangGraph's
checkpointer persists ``pending_trade`` for the next turn.

The turn ends with only the ``trade_intent`` block visible to the user. No
order has been placed; nothing downstream can place one until the user
confirms on the next turn.
"""

from src.agent.state import AssistantState


async def confirmation_gate_node(state: AssistantState) -> AssistantState:
    # The gate is intentionally a no-op. Its presence in the graph makes the
    # "trade agent produced a draft → turn ends" property explicit and
    # testable: graph assertions inspect the state this node returns.
    return state
