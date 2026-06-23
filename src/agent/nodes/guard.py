"""Guard node: topic classification + ticker extraction.

Uses the cheap guard model to classify the user's latest message. Ticker
extraction is deterministic regex so it can't hallucinate a symbol.
"""

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.prompts.guard import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_guard_model

_TICKER_RE = re.compile(r"\b[A-Z]{1,5}\b")
_TICKER_STOPWORDS: set[str] = {
    "A",
    "I",
    "AM",
    "AN",
    "AND",
    "ARE",
    "AS",
    "AT",
    "BE",
    "BUT",
    "BY",
    "DO",
    "FOR",
    "GO",
    "HAS",
    "HE",
    "HI",
    "IF",
    "IN",
    "IS",
    "IT",
    "ME",
    "MY",
    "NO",
    "NOT",
    "OF",
    "OK",
    "ON",
    "OR",
    "SO",
    "TO",
    "UP",
    "US",
    "WE",
    "WHAT",
    "WHEN",
    "WHERE",
    "WHO",
    "WHY",
    "HOW",
    "BUY",
    "SELL",
    "GET",
    "SET",
    "NEW",
    "YES",
    "YOU",
    "THE",
    "WAS",
    "HAD",
    "HAVE",
    "WILL",
    "CAN",
    "COULD",
    "SHOULD",
    "WOULD",
    "PLEASE",
    "OKAY",
    "CEO",
    "USD",
    "USA",
    "IPO",
    "ETF",
    "ETFS",
    "PE",
    "EPS",
    "ROI",
    "SEC",
    "FED",
    "GDP",
    "AI",
}
_CATEGORIES = {
    "news",
    "stock",
    "finance",
    "fundamentals",
    "estimates",
    "account",
    "trade",
    "off_topic",
}


def extract_tickers(text: str) -> list[str]:
    out: list[str] = []
    for match in _TICKER_RE.findall(text):
        if match in _TICKER_STOPWORDS:
            continue
        if match not in out:
            out.append(match)
    return out


def _parse_guard_response(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        # Drop optional leading "json"
        if "\n" in stripped:
            first, rest = stripped.split("\n", 1)
            if first.strip().lower() == "json":
                stripped = rest
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Fallback: find first JSON object in the text
        m = re.search(r"\{.*\}", stripped, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"category": "off_topic", "allowed": False, "reason": "unparseable"}


async def guard_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    user_input = state.get("user_input", "")
    llm = model or get_guard_model()
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_input)]
    response = await llm.ainvoke(messages)
    parsed = _parse_guard_response(
        response.content if hasattr(response, "content") else str(response)
    )

    category = parsed.get("category", "off_topic")
    if category not in _CATEGORIES:
        category = "off_topic"
    allowed = bool(parsed.get("allowed", category != "off_topic"))

    tickers = extract_tickers(user_input)
    existing = state.get("active_tickers") or []
    merged = list(dict.fromkeys(existing + tickers))

    state["category"] = category
    state["next_node"] = _category_to_node(category, allowed)
    state["active_tickers"] = merged
    state.setdefault("language", "en")
    state.setdefault("blocks", [])
    return state


def _category_to_node(category: str, allowed: bool) -> str:
    if not allowed or category == "off_topic":
        return "rejection"
    return {
        "news": "news_agent",
        "stock": "stock_agent",
        "finance": "finance_agent",
        "fundamentals": "fundamentals_agent",
        "estimates": "estimates_agent",
        "account": "account_agent",
        "trade": "trade_agent",
    }.get(category, "rejection")
