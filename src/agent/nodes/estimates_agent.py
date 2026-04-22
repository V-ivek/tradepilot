from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.nodes._agent_runner import run_tool_agent
from src.agent.prompts.estimates import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_agent_model
from src.tools.estimates.earnings import get_earnings
from src.tools.estimates.recommendations import get_recommendations
from src.tools.estimates.targets import get_targets

ESTIMATES_TOOLS = [get_earnings, get_recommendations, get_targets]


def _payload_to_table(payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None
    rows = [
        [str(k), str(v)] for k, v in payload.items() if k != "ticker" and v not in (None, {}, [])
    ]
    if not rows:
        return None
    return {"type": "table", "columns": ["field", "value"], "rows": rows}


async def estimates_agent_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_agent_model()
    tickers = state.get("active_tickers") or []
    context = f"Active tickers: {', '.join(tickers)}" if tickers else None

    final_text, tool_outputs = await run_tool_agent(
        model=llm,
        tools=ESTIMATES_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        user_input=state.get("user_input", ""),
        context_text=context,
    )

    blocks = state.setdefault("blocks", [])
    for _, payload in tool_outputs:
        block = _payload_to_table(payload)
        if block:
            blocks.append(block)

    if final_text:
        blocks.append({"type": "text", "content": final_text})
    return state
