from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.prompts.finance import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_agent_model


async def finance_agent_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_agent_model()
    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=state.get("user_input", "")),
        ]
    )
    content = response.content if hasattr(response, "content") else str(response)
    text = content if isinstance(content, str) else str(content)

    blocks = state.setdefault("blocks", [])
    blocks.append({"type": "text", "content": text})
    return state
