from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.nodes._agent_runner import run_tool_agent
from src.agent.prompts.account import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_agent_model
from src.tools.account.get_account import get_account
from src.tools.account.get_portfolio_history import get_portfolio_history
from src.tools.account.list_orders import list_orders
from src.tools.account.list_positions import list_positions

ACCOUNT_TOOLS = [get_account, list_positions, list_orders, get_portfolio_history]


def _account_to_block(payload: dict) -> dict | None:
    if not isinstance(payload, dict) or payload.get("equity") is None:
        return None
    return {
        "type": "account_summary",
        "equity": payload["equity"],
        "cash": payload.get("cash", "0"),
        "buying_power": payload.get("buying_power", "0"),
        "day_trade_count": int(payload.get("day_trade_count", 0)),
        "positions_count": int(payload.get("positions_count", 0)),
        "mode": "paper",
    }


def _positions_to_block(payload: list) -> dict | None:
    if not isinstance(payload, list) or not payload:
        return None
    rows = []
    for p in payload:
        if not isinstance(p, dict):
            continue
        rows.append(
            {
                "symbol": p.get("symbol", ""),
                "qty": p.get("qty", "0"),
                "avg_entry_price": p.get("avg_entry_price", "0"),
                "market_value": p.get("market_value", "0"),
                "unrealized_pl": p.get("unrealized_pl", "0"),
                "unrealized_plpc": p.get("unrealized_plpc", "0"),
            }
        )
    if not rows:
        return None
    return {"type": "positions_table", "rows": rows, "mode": "paper"}


async def account_agent_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_agent_model()
    final_text, tool_outputs = await run_tool_agent(
        model=llm,
        tools=ACCOUNT_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        user_input=state.get("user_input", ""),
    )

    blocks = state.setdefault("blocks", [])
    for tool_name, payload in tool_outputs:
        if tool_name == "get_account":
            block = _account_to_block(payload)
            if block:
                blocks.append(block)
        elif tool_name == "list_positions":
            block = _positions_to_block(payload)
            if block:
                blocks.append(block)

    if final_text:
        blocks.append({"type": "text", "content": final_text})
    return state
