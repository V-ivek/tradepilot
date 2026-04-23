"""Rule-based validator — the last node before a response leaves the graph.

Base rules (Phase 5):
1. Strip PII patterns (email, phone, SSN-shaped) from text blocks.
2. Inject a generic investment-advice disclaimer on any response containing
   quote/chart/table blocks if missing.
3. Drop blocks with empty required fields.

Paper-trading rules (Phase 6):
4. Trading blocks (``trade_intent``, ``order_result``, ``account_summary``,
   ``positions_table``) must carry ``mode == "paper"``; drop otherwise.
5. If any trading block is present, at least one text block must contain the
   phrase "paper trading" (case-insensitive); inject a disclaimer if missing.
6. Strip text blocks that claim an order was placed when no ``order_result``
   block accompanies them.
7. ``trade_intent`` blocks must have ``estimated_cost > 0``.
"""

import re
from decimal import Decimal, InvalidOperation

from src.agent.state import AssistantState

_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})(?!\d)"
)
_SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_FALSE_ORDER_CLAIM_RE = re.compile(
    r"\b(?:i\s+placed|i've\s+placed|i\s+submitted|order\s+(?:was|has\s+been)\s+(?:placed|submitted|executed|filled))\b",
    re.IGNORECASE,
)

_PII_REPLACEMENT = "[redacted]"

_DISCLAIMER = (
    "This is educational information, not personalized investment advice. "
    "Markets move; data can be delayed."
)
_PAPER_DISCLAIMER = "Paper trading only — no real money, no real orders."
_DISCLAIMER_TRIGGERS = {"quote", "chart", "table"}

TRADING_BLOCK_TYPES = {
    "trade_intent",
    "order_result",
    "account_summary",
    "positions_table",
}

_REQUIRED_BY_TYPE: dict[str, list[str]] = {
    "text": ["content"],
    "quote": ["symbol", "price"],
    "chart": ["symbol", "timeframe", "data"],
    "news_card": ["title", "url"],
    "table": ["columns", "rows"],
    "trade_intent": [
        "symbol",
        "side",
        "qty",
        "order_type",
        "estimated_cost",
        "confirmation_token",
    ],
    "order_result": ["order_id", "status", "filled_qty", "timestamp"],
    "account_summary": ["equity", "cash", "buying_power"],
    "positions_table": ["rows"],
}


def _scrub_pii(text: str) -> str:
    text = _EMAIL_RE.sub(_PII_REPLACEMENT, text)
    text = _SSN_RE.sub(_PII_REPLACEMENT, text)
    text = _PHONE_RE.sub(_PII_REPLACEMENT, text)
    return text


def _block_valid(block: dict) -> bool:
    btype = block.get("type")
    if btype not in _REQUIRED_BY_TYPE:
        return True
    for field in _REQUIRED_BY_TYPE[btype]:
        val = block.get(field)
        if val is None or val == "" or val == [] or val == {}:
            return False
    return True


def _trading_mode_ok(block: dict) -> bool:
    """Every trading-type block must carry mode='paper'."""
    if block.get("type") not in TRADING_BLOCK_TYPES:
        return True
    return block.get("mode") == "paper"


def _trade_intent_cost_positive(block: dict) -> bool:
    if block.get("type") != "trade_intent":
        return True
    try:
        return Decimal(str(block.get("estimated_cost", "0"))) > 0
    except (InvalidOperation, ValueError):
        return False


def _needs_base_disclaimer(blocks: list[dict]) -> bool:
    return any(b.get("type") in _DISCLAIMER_TRIGGERS for b in blocks)


def _has_trading_block(blocks: list[dict]) -> bool:
    return any(b.get("type") in TRADING_BLOCK_TYPES for b in blocks)


def _text_contains(blocks: list[dict], needle: str) -> bool:
    joined = " ".join(b.get("content", "") for b in blocks if b.get("type") == "text").lower()
    return needle.lower() in joined


def _strip_false_order_claims(blocks: list[dict]) -> list[dict]:
    has_result = any(b.get("type") == "order_result" for b in blocks)
    if has_result:
        return blocks
    out: list[dict] = []
    for b in blocks:
        if b.get("type") == "text" and isinstance(b.get("content"), str):
            if _FALSE_ORDER_CLAIM_RE.search(b["content"]):
                continue
        out.append(b)
    return out


async def validator_node(state: AssistantState) -> AssistantState:
    blocks = state.get("blocks") or []
    cleaned: list[dict] = []
    for b in blocks:
        if not _block_valid(b):
            continue
        if not _trading_mode_ok(b):
            continue
        if not _trade_intent_cost_positive(b):
            continue
        if b.get("type") == "text" and isinstance(b.get("content"), str):
            b = {**b, "content": _scrub_pii(b["content"])}
        cleaned.append(b)

    cleaned = _strip_false_order_claims(cleaned)

    if _needs_base_disclaimer(cleaned):
        if not _text_contains(cleaned, "educational") and not _text_contains(
            cleaned, "not personalized"
        ):
            cleaned.append({"type": "text", "content": _DISCLAIMER})

    if _has_trading_block(cleaned):
        if not _text_contains(cleaned, "paper trading"):
            cleaned.insert(0, {"type": "text", "content": _PAPER_DISCLAIMER})

    state["blocks"] = cleaned
    return state
