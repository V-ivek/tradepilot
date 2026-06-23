from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.nodes._agent_runner import run_tool_agent
from src.agent.prompts.news import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_agent_model
from src.tools.news.alpaca_news import search_news
from src.tools.news.trending import get_trending_news
from src.tools.stocks.stock_news import get_stock_news

NEWS_TOOLS = [search_news, get_trending_news, get_stock_news]


def _article_to_block(article: dict) -> dict:
    return {
        "type": "news_card",
        "title": article.get("title", ""),
        "summary": article.get("summary") or "",
        "url": article.get("url", ""),
        "source": article.get("source", ""),
        "published_at": article.get("published_at"),
        "tickers": article.get("tickers") or [],
    }


async def news_agent_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_agent_model()
    tickers = state.get("active_tickers") or []
    context = f"Active tickers in this conversation: {', '.join(tickers)}" if tickers else None

    final_text, tool_outputs = await run_tool_agent(
        model=llm,
        tools=NEWS_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        user_input=state.get("user_input", ""),
        context_text=context,
    )

    blocks = state.setdefault("blocks", [])
    for _, payload in tool_outputs:
        if not isinstance(payload, list):
            continue
        for article in payload:
            if isinstance(article, dict) and article.get("url"):
                blocks.append(_article_to_block(article))

    if final_text:
        blocks.append({"type": "text", "content": final_text})
    return state
