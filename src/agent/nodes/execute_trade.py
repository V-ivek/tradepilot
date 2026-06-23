"""Execute trade node.

Preconditions checked in order:
1. ``pending_trade`` and ``awaiting_confirmation`` both set.
2. Draft shape is valid (Pydantic).
3. HMAC token matches; draft hasn't expired.
4. Gateway accepts the order.

Any failure emits a ``text`` block with a user-readable error and clears the
pending-trade state. The happy path emits an ``order_result`` block and clears.
"""

from decimal import Decimal

from pydantic import ValidationError

from gateway.services.paper_trading import OrderRequest
from src.agent.state import AssistantState
from src.config.settings import get_settings
from src.models.order import OrderDraft, verify_order_token
from src.services.gateway import get_gateway_client


def _clear(state: AssistantState) -> None:
    state["pending_trade"] = None
    state["awaiting_confirmation"] = False


def _draft_to_request(draft: OrderDraft) -> OrderRequest:
    return OrderRequest(
        symbol=draft.symbol,
        side=draft.side,
        qty=Decimal(draft.qty),
        type=draft.type,
        limit_price=draft.limit_price,
        stop_price=draft.stop_price,
        time_in_force=draft.time_in_force,
    )


async def execute_trade_node(state: AssistantState) -> AssistantState:
    blocks = state.setdefault("blocks", [])
    draft_data = state.get("pending_trade")
    if not draft_data or not state.get("awaiting_confirmation"):
        blocks.append({"type": "text", "content": "No order to confirm."})
        return state

    try:
        draft = OrderDraft.model_validate(draft_data)
    except ValidationError:
        blocks.append({"type": "text", "content": "Invalid pending order; please restate."})
        _clear(state)
        return state

    if not verify_order_token(draft, get_settings().jwt_secret):
        blocks.append(
            {"type": "text", "content": "Order draft expired or tampered. Please restate."}
        )
        _clear(state)
        return state

    gateway = get_gateway_client()
    try:
        result = await gateway.place_order(_draft_to_request(draft))
    except Exception as e:
        blocks.append({"type": "text", "content": f"Order failed: {e}"})
        _clear(state)
        return state

    if result is None:
        blocks.append({"type": "text", "content": "Order failed: gateway returned no result."})
        _clear(state)
        return state

    blocks.append(
        {
            "type": "order_result",
            "order_id": result.order_id,
            "status": result.status,
            "filled_qty": str(result.filled_qty),
            "filled_avg_price": str(result.filled_avg_price) if result.filled_avg_price else None,
            "timestamp": result.submitted_at.isoformat(),
            "mode": "paper",
        }
    )
    _clear(state)
    return state
