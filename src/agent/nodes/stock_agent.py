from decimal import Decimal, InvalidOperation

from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.nodes._agent_runner import run_tool_agent
from src.agent.prompts.stock import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_agent_model
from src.tools.stocks.lookup import lookup_stock
from src.tools.stocks.price_history import get_price_history
from src.tools.stocks.search import search_stock
from src.tools.stocks.stock_news import get_stock_news

STOCK_TOOLS = [lookup_stock, search_stock, get_price_history, get_stock_news]


def _as_decimal(v) -> Decimal:
    if v is None:
        return Decimal("0")
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _quote_to_block(q: dict) -> dict | None:
    if not isinstance(q, dict) or not q.get("price"):
        return None
    return {
        "type": "quote",
        "symbol": q.get("ticker", ""),
        "price": q["price"],
        "change": str(_as_decimal(q.get("change"))),
        "change_pct": str(_as_decimal(q.get("change_pct"))),
    }


def _bars_to_chart_block(bars: list[dict], symbol: str, period: str = "1M") -> dict | None:
    if not bars:
        return None
    return {"type": "chart", "symbol": symbol, "timeframe": period, "data": bars}


async def stock_agent_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_agent_model()
    tickers = state.get("active_tickers") or []
    context = f"Active tickers: {', '.join(tickers)}" if tickers else None

    final_text, tool_outputs = await run_tool_agent(
        model=llm,
        tools=STOCK_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        user_input=state.get("user_input", ""),
        context_text=context,
    )

    blocks = state.setdefault("blocks", [])
    for tool_name, payload in tool_outputs:
        if tool_name == "lookup_stock":
            block = _quote_to_block(payload)
            if block:
                blocks.append(block)
        elif tool_name == "get_price_history" and isinstance(payload, list):
            symbol = tickers[0] if tickers else ""
            block = _bars_to_chart_block(payload, symbol)
            if block:
                blocks.append(block)

    if final_text:
        blocks.append({"type": "text", "content": final_text})
    return state
