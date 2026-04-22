from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.nodes._agent_runner import run_tool_agent
from src.agent.prompts.fundamentals import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_agent_model
from src.tools.fundamentals.analyst import get_analyst
from src.tools.fundamentals.filings import get_filings
from src.tools.fundamentals.ratios import get_ratios
from src.tools.fundamentals.segments import get_segments
from src.tools.fundamentals.shares import get_shares
from src.tools.fundamentals.statements import get_statements

FUNDAMENTALS_TOOLS = [
    get_ratios,
    get_statements,
    get_analyst,
    get_shares,
    get_filings,
    get_segments,
]


def _metrics_to_table(payload: dict) -> dict | None:
    metrics = payload.get("metrics") if isinstance(payload, dict) else None
    if not metrics:
        return None
    rows = [[str(k), str(v)] for k, v in metrics.items() if v is not None]
    if not rows:
        return None
    return {"type": "table", "columns": ["metric", "value"], "rows": rows}


async def fundamentals_agent_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_agent_model()
    tickers = state.get("active_tickers") or []
    context = f"Active tickers: {', '.join(tickers)}" if tickers else None

    final_text, tool_outputs = await run_tool_agent(
        model=llm,
        tools=FUNDAMENTALS_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        user_input=state.get("user_input", ""),
        context_text=context,
    )

    blocks = state.setdefault("blocks", [])
    for _, payload in tool_outputs:
        block = _metrics_to_table(payload)
        if block:
            blocks.append(block)

    if final_text:
        blocks.append({"type": "text", "content": final_text})
    return state
