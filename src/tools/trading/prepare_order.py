"""``prepare_order`` — the LLM-facing tool that validates an order and returns
a signed draft. Does NOT place the order. The user must confirm on the next
turn before the confirmation gate will release it.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from langchain_core.tools import tool

from src.config.settings import get_settings
from src.models.order import OrderDraft, new_nonce, sign_order
from src.services.gateway import GatewayClient, get_gateway_client


def _to_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


async def _impl(
    gateway: GatewayClient,
    secret: str,
    *,
    symbol: str,
    side: str,
    qty: str,
    type: str,
    limit_price: str | None = None,
    stop_price: str | None = None,
    time_in_force: str = "day",
) -> dict:
    sym = symbol.upper().strip()
    qty_d = _to_decimal(qty)
    if qty_d is None or qty_d <= 0:
        return {"error": f"Invalid quantity: {qty}"}

    # 1. Validate symbol exists
    matches = await gateway.search_symbols(sym, limit=5)
    if not any(m.ticker.upper() == sym for m in matches):
        return {"error": f"Unknown symbol: {sym}"}

    # 2. Estimate cost from quote (or limit price)
    limit_d = _to_decimal(limit_price) if limit_price else None
    stop_d = _to_decimal(stop_price) if stop_price else None
    quote = await gateway.get_quote(sym)
    if limit_d is not None:
        estimated = qty_d * limit_d
    elif quote is not None:
        estimated = qty_d * quote.price
    else:
        return {"error": f"No quote for {sym}; cannot estimate cost."}

    # 3. Buying-power check for buys
    if side == "buy":
        account = await gateway.get_account()
        if account is None:
            return {"error": "Could not fetch account for buying-power check."}
        if estimated > account.buying_power:
            return {
                "error": (
                    f"Insufficient buying power: need {estimated}, have {account.buying_power}"
                )
            }

    # 4. Build and sign the draft
    nonce = new_nonce()
    now = datetime.now(timezone.utc)
    draft_data = {
        "symbol": sym,
        "side": side,
        "qty": qty_d,
        "type": type,
        "limit_price": limit_d,
        "stop_price": stop_d,
        "time_in_force": time_in_force,
        "estimated_cost": estimated,
        "nonce": nonce,
        "created_at": now,
        "mode": "paper",
    }
    token = sign_order(draft_data, secret)
    try:
        draft = OrderDraft(**draft_data, confirmation_token=token)
    except Exception as e:
        return {"error": f"Invalid draft: {e}"}
    return draft.model_dump(mode="json")


@tool
async def prepare_order(
    symbol: str,
    side: str,
    qty: str,
    type: str,
    limit_price: str | None = None,
    stop_price: str | None = None,
    time_in_force: str = "day",
) -> dict:
    """Validate an order and return a signed draft for confirmation (does NOT place)."""
    return await _impl(
        get_gateway_client(),
        get_settings().jwt_secret,
        symbol=symbol,
        side=side,
        qty=qty,
        type=type,
        limit_price=limit_price,
        stop_price=stop_price,
        time_in_force=time_in_force,
    )
