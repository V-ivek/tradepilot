from unittest.mock import AsyncMock, patch

from src.agent.nodes.account_agent import account_agent_node


async def test_account_agent_emits_account_summary_block():
    tool_outputs = [
        (
            "get_account",
            {
                "equity": "100000",
                "cash": "50000",
                "buying_power": "50000",
                "day_trade_count": 0,
                "positions_count": 2,
                "mode": "paper",
            },
        )
    ]
    with patch(
        "src.agent.nodes.account_agent.run_tool_agent",
        new=AsyncMock(return_value=("Your paper account has $50k cash.", tool_outputs)),
    ):
        out = await account_agent_node({"user_input": "my account"}, model=object())

    summary = next(b for b in out["blocks"] if b["type"] == "account_summary")
    assert summary["mode"] == "paper"
    assert summary["cash"] == "50000"


async def test_account_agent_emits_positions_table_block():
    tool_outputs = [
        (
            "list_positions",
            [
                {
                    "symbol": "AAPL",
                    "qty": "10",
                    "avg_entry_price": "180",
                    "market_value": "1900",
                    "unrealized_pl": "100",
                    "unrealized_plpc": "0.05",
                }
            ],
        )
    ]
    with patch(
        "src.agent.nodes.account_agent.run_tool_agent",
        new=AsyncMock(return_value=("You hold 10 AAPL.", tool_outputs)),
    ):
        out = await account_agent_node({"user_input": "my positions"}, model=object())

    table = next(b for b in out["blocks"] if b["type"] == "positions_table")
    assert table["mode"] == "paper"
    assert table["rows"][0]["symbol"] == "AAPL"


async def test_account_agent_skips_empty_payloads():
    tool_outputs = [("get_account", {}), ("list_positions", [])]
    with patch(
        "src.agent.nodes.account_agent.run_tool_agent",
        new=AsyncMock(return_value=("Nothing yet.", tool_outputs)),
    ):
        out = await account_agent_node({"user_input": "x"}, model=object())

    types = {b["type"] for b in out["blocks"]}
    assert types == {"text"}
