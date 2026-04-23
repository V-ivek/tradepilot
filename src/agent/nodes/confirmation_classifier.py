"""Confirmation classifier node.

Uses the cheap guard model. Classifies the user's reply-to-pending-order into
one of AFFIRM / DENY / MODIFY / UNRELATED. For MODIFY, extracts `edits` dict.
"""

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.prompts.confirmation_classifier import SYSTEM_PROMPT
from src.agent.state import AssistantState
from src.services.llm import get_guard_model

VALID_VERDICTS = {"AFFIRM", "DENY", "MODIFY", "UNRELATED"}


def _parse(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if "\n" in stripped:
            first, rest = stripped.split("\n", 1)
            if first.strip().lower() == "json":
                stripped = rest
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", stripped, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"verdict": "UNRELATED"}


async def confirmation_classifier_node(
    state: AssistantState, *, model: BaseChatModel | None = None
) -> AssistantState:
    llm = model or get_guard_model()
    user_input = state.get("user_input", "")
    response = await llm.ainvoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_input)]
    )
    content = response.content if hasattr(response, "content") else str(response)
    parsed = _parse(content if isinstance(content, str) else str(content))

    verdict = parsed.get("verdict", "UNRELATED")
    if verdict not in VALID_VERDICTS:
        verdict = "UNRELATED"
    state["confirmation_verdict"] = verdict

    edits = parsed.get("edits")
    if verdict == "MODIFY" and isinstance(edits, dict) and edits:
        state["pending_edits"] = edits  # picked up by trade_agent on re-entry
    return state
