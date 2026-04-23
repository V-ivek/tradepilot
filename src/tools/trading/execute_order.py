"""``execute_order`` — only called from the ``execute_trade`` node AFTER the
confirmation classifier has returned AFFIRM. Re-verifies the HMAC token and
TTL before hitting Alpaca.
"""

from decimal import Decimal

from pydantic import ValidationError

from gateway.services.paper_trading import OrderRequest
from src.models.order import OrderDraft, verify_order_token
from src.services.gateway import GatewayClient


def _draft_to_order_request(draft: OrderDraft) -> OrderRequest:
    return OrderRequest(
        symbol=draft.symbol,
        side=draft.side,
        qty=Decimal(draft.qty),
        type=draft.type,
        limit_price=draft.limit_price,
        stop_price=draft.stop_price,
        time_in_force=draft.time_in_force,
    )


async def _impl(gateway: GatewayClient, secret: str, draft_data: dict) -> dict:
    try:
        draft = OrderDraft.model_validate(draft_data)
    except ValidationError as e:
        return {"error": f"Invalid draft: {e}"}

    if not verify_order_token(draft, secret):
        return {"error": "draft expired or tampered"}

    try:
        result = await gateway.place_order(_draft_to_order_request(draft))
    except Exception as e:  # gateway client is defensive, but belt-and-braces
        return {"error": f"order failed: {e}"}

    if result is None:
        return {"error": "order failed: gateway returned no result"}

    return result.model_dump(mode="json")
