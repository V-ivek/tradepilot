from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage

from src.agent.nodes.guard import extract_tickers, guard_node
from src.agent.state import AssistantState


def _llm_returning(content: str):
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


async def test_on_topic_allowed_routes_to_stock_agent():
    state: AssistantState = {"user_input": "What's AAPL's price?"}
    llm = _llm_returning('{"category": "stock", "allowed": true, "reason": "ok"}')

    out = await guard_node(state, model=llm)

    assert out["category"] == "stock"
    assert out["next_node"] == "stock_agent"
    assert "AAPL" in out["active_tickers"]


async def test_off_topic_routes_to_rejection():
    state: AssistantState = {"user_input": "What's the weather?"}
    llm = _llm_returning('{"category": "off_topic", "allowed": false, "reason": "nope"}')

    out = await guard_node(state, model=llm)

    assert out["category"] == "off_topic"
    assert out["next_node"] == "rejection"


async def test_trade_category_routes_to_trade_agent():
    state: AssistantState = {"user_input": "Buy 10 TSLA at market"}
    llm = _llm_returning('{"category": "trade", "allowed": true, "reason": "ok"}')

    out = await guard_node(state, model=llm)

    assert out["next_node"] == "trade_agent"
    assert "TSLA" in out["active_tickers"]


async def test_handles_markdown_code_fences():
    state: AssistantState = {"user_input": "AAPL price"}
    llm = _llm_returning('```json\n{"category": "stock", "allowed": true, "reason": "ok"}\n```')

    out = await guard_node(state, model=llm)

    assert out["category"] == "stock"


async def test_unparseable_response_defaults_to_off_topic():
    state: AssistantState = {"user_input": "foo"}
    llm = _llm_returning("nothing useful here")

    out = await guard_node(state, model=llm)

    assert out["category"] == "off_topic"
    assert out["next_node"] == "rejection"


async def test_invalid_category_defaults_to_off_topic():
    state: AssistantState = {"user_input": "foo"}
    llm = _llm_returning('{"category": "weather", "allowed": true}')

    out = await guard_node(state, model=llm)

    assert out["category"] == "off_topic"


def test_extract_tickers_picks_up_symbols():
    assert "AAPL" in extract_tickers("What is AAPL's price?")
    assert "TSLA" in extract_tickers("Buy 10 TSLA")


def test_extract_tickers_ignores_common_words():
    assert extract_tickers("I can buy a stock") == []
    assert "BUY" not in extract_tickers("buy AAPL")


def test_extract_tickers_deduplicates_preserving_order():
    out = extract_tickers("AAPL then TSLA then AAPL")
    assert out == ["AAPL", "TSLA"]


def test_extract_tickers_case_sensitive_only_uppercase():
    assert extract_tickers("aapl is here") == []


async def test_active_tickers_merged_with_existing():
    state: AssistantState = {"user_input": "TSLA price", "active_tickers": ["AAPL"]}
    llm = _llm_returning('{"category": "stock", "allowed": true}')

    out = await guard_node(state, model=llm)

    assert out["active_tickers"] == ["AAPL", "TSLA"]
