from unittest.mock import AsyncMock, patch

from src.agent.nodes.news_agent import news_agent_node
from src.agent.state import AssistantState


async def test_news_agent_builds_news_card_blocks():
    tool_outputs = [
        (
            "get_stock_news",
            [
                {
                    "title": "Apple up",
                    "summary": "s1",
                    "url": "https://n/1",
                    "source": "wire",
                    "published_at": "2026-04-22T10:00:00+00:00",
                    "tickers": ["AAPL"],
                }
            ],
        )
    ]
    with patch(
        "src.agent.nodes.news_agent.run_tool_agent",
        new=AsyncMock(return_value=("Apple rose on good news.", tool_outputs)),
    ):
        state: AssistantState = {"user_input": "AAPL news", "active_tickers": ["AAPL"]}
        out = await news_agent_node(state, model=object())

    types = [b["type"] for b in out["blocks"]]
    assert "news_card" in types
    assert "text" in types
    card = next(b for b in out["blocks"] if b["type"] == "news_card")
    assert card["title"] == "Apple up"


async def test_news_agent_drops_articles_without_url():
    tool_outputs = [("get_trending_news", [{"title": "no url"}, {"title": "ok", "url": "x"}])]
    with patch(
        "src.agent.nodes.news_agent.run_tool_agent",
        new=AsyncMock(return_value=("", tool_outputs)),
    ):
        state: AssistantState = {"user_input": "news"}
        out = await news_agent_node(state, model=object())

    cards = [b for b in out["blocks"] if b["type"] == "news_card"]
    assert len(cards) == 1
    assert cards[0]["title"] == "ok"


async def test_news_agent_empty_tool_output():
    with patch(
        "src.agent.nodes.news_agent.run_tool_agent",
        new=AsyncMock(return_value=("No news.", [])),
    ):
        state: AssistantState = {"user_input": "news"}
        out = await news_agent_node(state, model=object())

    assert [b["type"] for b in out["blocks"]] == ["text"]
