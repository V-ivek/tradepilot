from unittest.mock import AsyncMock, patch

from src.agent.nodes.fundamentals_agent import fundamentals_agent_node


async def test_fundamentals_agent_emits_table_block():
    tool_outputs = [
        (
            "get_ratios",
            {
                "ticker": "AAPL",
                "period": "annual",
                "metrics": {"peBasicExtraTTM": "28.5", "pbRatio": "42.1"},
            },
        )
    ]
    with patch(
        "src.agent.nodes.fundamentals_agent.run_tool_agent",
        new=AsyncMock(return_value=("AAPL trades at 28.5x earnings.", tool_outputs)),
    ):
        out = await fundamentals_agent_node(
            {"user_input": "AAPL ratios", "active_tickers": ["AAPL"]},
            model=object(),
        )

    types = [b["type"] for b in out["blocks"]]
    assert "table" in types
    assert "text" in types


async def test_fundamentals_agent_skips_empty_metrics():
    tool_outputs = [("get_shares", {"ticker": "AAPL", "metrics": {}})]
    with patch(
        "src.agent.nodes.fundamentals_agent.run_tool_agent",
        new=AsyncMock(return_value=("no data", tool_outputs)),
    ):
        out = await fundamentals_agent_node({"user_input": "x"}, model=object())

    types = [b["type"] for b in out["blocks"]]
    assert "table" not in types
