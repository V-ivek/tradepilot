"""Rule-based validator — the last node before a response leaves the graph.

Base rules in v0.1:
1. Strip PII patterns (email, phone, SSN-shaped) from text blocks.
2. Inject a generic investment-advice disclaimer on any response containing
   quote/chart/fundamentals blocks if missing.
3. Drop blocks with empty required fields (trade_intent missing estimated_cost, etc.).

Paper-trading rules (added in Phase 6) are applied after the base rules.
"""

import re

from src.agent.state import AssistantState

_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})(?!\d)"
)
_SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

_PII_REPLACEMENT = "[redacted]"

_DISCLAIMER = (
    "This is educational information, not personalized investment advice. "
    "Markets move; data can be delayed."
)
_DISCLAIMER_TRIGGERS = {"quote", "chart", "table"}

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


def _needs_disclaimer(blocks: list[dict]) -> bool:
    return any(b.get("type") in _DISCLAIMER_TRIGGERS for b in blocks)


async def validator_node(state: AssistantState) -> AssistantState:
    blocks = state.get("blocks") or []
    cleaned: list[dict] = []
    for b in blocks:
        if not _block_valid(b):
            continue
        if b.get("type") == "text" and isinstance(b.get("content"), str):
            b = {**b, "content": _scrub_pii(b["content"])}
        cleaned.append(b)

    if _needs_disclaimer(cleaned):
        joined = " ".join(b.get("content", "") for b in cleaned if b.get("type") == "text").lower()
        if "educational" not in joined and "not personalized" not in joined:
            cleaned.append({"type": "text", "content": _DISCLAIMER})

    state["blocks"] = cleaned
    return state
