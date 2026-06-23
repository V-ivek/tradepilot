from unittest.mock import AsyncMock, patch

from src.agent.nodes.estimates_agent import estimates_agent_node


async def test_estimates_agent_emits_table_block():
    tool_outputs = [
        (
            "get_targets",
            {
                "ticker": "AAPL",
                "price_target_mean": "210",
                "price_target_high": "260",
                "price_target_low": "180",
                "analyst_count": 30,
            },
        )
    ]
    with patch(
        "src.agent.nodes.estimates_agent.run_tool_agent",
        new=AsyncMock(return_value=("Mean target: $210.", tool_outputs)),
    ):
        out = await estimates_agent_node(
            {"user_input": "AAPL targets", "active_tickers": ["AAPL"]},
            model=object(),
        )

    types = [b["type"] for b in out["blocks"]]
    assert "table" in types
    assert "text" in types


async def test_estimates_agent_skips_empty_payload():
    tool_outputs = [("get_recommendations", {"ticker": "AAPL", "recommendations": {}})]
    with patch(
        "src.agent.nodes.estimates_agent.run_tool_agent",
        new=AsyncMock(return_value=("no coverage", tool_outputs)),
    ):
        out = await estimates_agent_node({"user_input": "x"}, model=object())

    types = [b["type"] for b in out["blocks"]]
    assert "table" not in types
