from unittest.mock import AsyncMock, patch

from src.agent.nodes.stock_agent import stock_agent_node


async def test_stock_agent_emits_quote_block():
    tool_outputs = [
        (
            "lookup_stock",
            {"ticker": "AAPL", "price": "189.55", "change": "1.23", "change_pct": "0.65"},
        )
    ]
    with patch(
        "src.agent.nodes.stock_agent.run_tool_agent",
        new=AsyncMock(return_value=("AAPL is at $189.55.", tool_outputs)),
    ):
        out = await stock_agent_node(
            {"user_input": "AAPL price", "active_tickers": ["AAPL"]},
            model=object(),
        )

    types = [b["type"] for b in out["blocks"]]
    assert "quote" in types
    quote = next(b for b in out["blocks"] if b["type"] == "quote")
    assert quote["symbol"] == "AAPL"


async def test_stock_agent_emits_chart_block_for_price_history():
    tool_outputs = [
        (
            "get_price_history",
            [{"timestamp": "2026-04-22T00:00:00+00:00", "close": "100"}],
        )
    ]
    with patch(
        "src.agent.nodes.stock_agent.run_tool_agent",
        new=AsyncMock(return_value=("", tool_outputs)),
    ):
        out = await stock_agent_node(
            {"user_input": "AAPL 1M chart", "active_tickers": ["AAPL"]},
            model=object(),
        )

    chart = next(b for b in out["blocks"] if b["type"] == "chart")
    assert chart["symbol"] == "AAPL"


async def test_stock_agent_drops_quote_without_price():
    tool_outputs = [("lookup_stock", {})]
    with patch(
        "src.agent.nodes.stock_agent.run_tool_agent",
        new=AsyncMock(return_value=("No data.", tool_outputs)),
    ):
        out = await stock_agent_node({"user_input": "x"}, model=object())

    assert all(b["type"] != "quote" for b in out["blocks"])


async def test_stock_agent_appends_text_summary():
    with patch(
        "src.agent.nodes.stock_agent.run_tool_agent",
        new=AsyncMock(return_value=("summary", [])),
    ):
        out = await stock_agent_node({"user_input": "x"}, model=object())

    assert out["blocks"][-1] == {"type": "text", "content": "summary"}
