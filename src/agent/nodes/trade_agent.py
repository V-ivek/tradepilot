"""Trade agent — parses a user's order request, calls ``prepare_order``, and
emits a ``trade_intent`` block. Does NOT place the order; the confirmation
gate halts the graph at this point until the user's next turn.
"""

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.prompts.trade import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.config.settings import get_settings
from src.services.gateway import get_gateway_client
from src.services.llm import get_agent_model
from src.tools.trading.prepare_order import _impl as prepare_order_impl

_EXTRACTOR_PROMPT = """\
Extract the order parameters from the user's message. Return ONLY a JSON object
with these keys (omit keys the user didn't specify):
{
  "symbol": "<uppercase US ticker>",
  "side": "buy" | "sell",
  "qty": "<positive number as string>",
  "type": "market" | "limit" | "stop" | "stop_limit",
  "limit_price": "<number as string>",
  "stop_price": "<number as string>",
  "time_in_force": "day" | "gtc" | "ioc" | "fok"
}
If a required field (symbol, side, qty, type) is missing, return
{"error": "<short human message telling the user what's missing>"}.
Default `type` to "market" if the user didn't specify one.
Default `side` only if the verb was explicit ("buy", "sell").
"""

_REQUIRED_ARGS = {"symbol", "side", "qty", "type"}


def _parse_extractor(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if "\n" in stripped:
            first, rest = stripped.split("\n", 1)
            if first.strip().lower() == "json":
                stripped = rest
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {"error": "I couldn't understand the order. Please restate it."}


async def extract_order_args(model: BaseChatModel, user_input: str) -> dict[str, Any]:
    response = await model.ainvoke(
        [
            SystemMessage(content=_EXTRACTOR_PROMPT),
            HumanMessage(content=user_input),
        ]
    )
    content = response.content if hasattr(response, "content") else str(response)
    parsed = _parse_extractor(content if isinstance(content, str) else str(content))
    if "error" in parsed:
        return parsed
    missing = _REQUIRED_ARGS - set(parsed.keys())
    if missing:
        return {
            "error": (
                "Missing order fields: " + ", ".join(sorted(missing)) + ". Please specify them."
            )
        }
    return parsed


def _draft_to_intent_block(draft: dict) -> dict:
    return {
        "type": "trade_intent",
        "symbol": draft["symbol"],
        "side": draft["side"],
        "qty": draft["qty"],
        "order_type": draft["type"],
        "limit_price": draft.get("limit_price"),
        "stop_price": draft.get("stop_price"),
        "time_in_force": draft.get("time_in_force", "day"),
        "estimated_cost": draft["estimated_cost"],
        "confirmation_token": draft["confirmation_token"],
        "mode": "paper",
    }


async def trade_agent_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_agent_model()
    # Mostly the system prompt is for the user-facing message; extraction uses
    # a separate deterministic prompt.
    _ = SYSTEM_PROMPT

    user_input = state.get("user_input", "")
    blocks = state.setdefault("blocks", [])

    args = await extract_order_args(llm, user_input)
    if "error" in args:
        blocks.append({"type": "text", "content": args["error"]})
        return state

    gateway = get_gateway_client()
    secret = get_settings().jwt_secret
    draft = await prepare_order_impl(gateway, secret, **args)
    if "error" in draft:
        blocks.append({"type": "text", "content": draft["error"]})
        return state

    blocks.append(_draft_to_intent_block(draft))
    state["pending_trade"] = draft
    state["awaiting_confirmation"] = True

    confirm_text = (
        f"Confirm PAPER order: {args['side'].upper()} {args['qty']} {args['symbol']} "
        f"@ {args['type']}. Reply 'confirm' to place (paper only — no real money)."
    )
    blocks.append({"type": "text", "content": confirm_text})
    return state
