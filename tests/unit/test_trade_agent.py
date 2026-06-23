from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from src.agent.nodes.trade_agent import extract_order_args, trade_agent_node
from src.agent.state import AssistantState


def _extractor_llm(content: str):
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


async def test_extract_order_args_happy():
    llm = _extractor_llm('{"symbol": "TSLA", "side": "buy", "qty": "10", "type": "market"}')
    args = await extract_order_args(llm, "buy 10 TSLA at market")

    assert args == {"symbol": "TSLA", "side": "buy", "qty": "10", "type": "market"}


async def test_extract_order_args_missing_side():
    llm = _extractor_llm('{"symbol": "TSLA", "qty": "10", "type": "market"}')
    args = await extract_order_args(llm, "TSLA 10")

    assert "error" in args
    assert "side" in args["error"]


async def test_extract_order_args_handles_code_fence():
    llm = _extractor_llm(
        '```json\n{"symbol": "TSLA", "side": "buy", "qty": "10", "type": "market"}\n```'
    )
    args = await extract_order_args(llm, "x")

    assert args["symbol"] == "TSLA"


async def test_extract_order_args_returns_error_on_unparseable():
    llm = _extractor_llm("what?")
    args = await extract_order_args(llm, "buy something")

    assert "error" in args


async def test_trade_agent_happy_path():
    draft = {
        "symbol": "TSLA",
        "side": "buy",
        "qty": "10",
        "type": "market",
        "limit_price": None,
        "stop_price": None,
        "time_in_force": "day",
        "estimated_cost": "2000",
        "confirmation_token": "tok",
        "nonce": "n",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
    }
    llm = _extractor_llm('{"symbol": "TSLA", "side": "buy", "qty": "10", "type": "market"}')
    with (
        patch(
            "src.agent.nodes.trade_agent.prepare_order_impl",
            new=AsyncMock(return_value=draft),
        ),
        patch("src.agent.nodes.trade_agent.get_gateway_client", return_value=None),
        patch(
            "src.agent.nodes.trade_agent.get_settings",
            return_value=type("S", (), {"jwt_secret": "s"}),
        ),
    ):
        state: AssistantState = {"user_input": "buy 10 TSLA"}
        out = await trade_agent_node(state, model=llm)

    assert out["pending_trade"] == draft
    assert out["awaiting_confirmation"] is True
    types = [b["type"] for b in out["blocks"]]
    assert "trade_intent" in types
    intent = next(b for b in out["blocks"] if b["type"] == "trade_intent")
    assert intent["mode"] == "paper"
    assert intent["confirmation_token"] == "tok"
    # Confirmation copy references "paper"
    texts = [b["content"] for b in out["blocks"] if b["type"] == "text"]
    assert any("paper" in t.lower() for t in texts)


async def test_trade_agent_unknown_symbol_returns_text_no_pending():
    llm = _extractor_llm('{"symbol": "ZZZ", "side": "buy", "qty": "1", "type": "market"}')
    with (
        patch(
            "src.agent.nodes.trade_agent.prepare_order_impl",
            new=AsyncMock(return_value={"error": "Unknown symbol: ZZZ"}),
        ),
        patch("src.agent.nodes.trade_agent.get_gateway_client", return_value=None),
        patch(
            "src.agent.nodes.trade_agent.get_settings",
            return_value=type("S", (), {"jwt_secret": "s"}),
        ),
    ):
        state: AssistantState = {"user_input": "buy 1 ZZZ"}
        out = await trade_agent_node(state, model=llm)

    assert "pending_trade" not in out or out.get("pending_trade") is None
    assert not out.get("awaiting_confirmation")
    types = [b["type"] for b in out["blocks"]]
    assert types == ["text"]


async def test_trade_agent_insufficient_buying_power_returns_text():
    llm = _extractor_llm('{"symbol": "AAPL", "side": "buy", "qty": "1000", "type": "market"}')
    with (
        patch(
            "src.agent.nodes.trade_agent.prepare_order_impl",
            new=AsyncMock(
                return_value={"error": "Insufficient buying power: need 180000, have 50000"}
            ),
        ),
        patch("src.agent.nodes.trade_agent.get_gateway_client", return_value=None),
        patch(
            "src.agent.nodes.trade_agent.get_settings",
            return_value=type("S", (), {"jwt_secret": "s"}),
        ),
    ):
        state: AssistantState = {"user_input": "buy 1000 AAPL"}
        out = await trade_agent_node(state, model=llm)

    assert not out.get("awaiting_confirmation")
    text = out["blocks"][0]["content"]
    assert "Insufficient" in text


async def test_trade_agent_extraction_error_returns_text():
    llm = _extractor_llm('{"symbol": "AAPL", "qty": "1"}')  # missing side, type
    state: AssistantState = {"user_input": "something"}

    out = await trade_agent_node(state, model=llm)

    assert not out.get("awaiting_confirmation")
    assert out["blocks"][0]["type"] == "text"
