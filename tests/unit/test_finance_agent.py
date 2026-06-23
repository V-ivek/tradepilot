from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage

from src.agent.nodes.finance_agent import finance_agent_node


async def test_finance_agent_emits_text_block():
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="An ETF is..."))

    out = await finance_agent_node({"user_input": "What's an ETF?"}, model=llm)

    assert len(out["blocks"]) == 1
    assert out["blocks"][0] == {"type": "text", "content": "An ETF is..."}
