"""Rejection node: emits a polite off-topic text block. No LLM call."""

from src.agent.prompts.rejection import REJECTION_TEXT
from src.agent.state import AssistantState


async def rejection_node(state: AssistantState) -> AssistantState:
    blocks = state.setdefault("blocks", [])
    blocks.append({"type": "text", "content": REJECTION_TEXT})
    return state
