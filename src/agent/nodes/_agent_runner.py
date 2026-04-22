"""Shared helper that runs a ReAct-style tool-calling agent and returns the
final text + the tool-message payloads so specialist nodes can build blocks
from raw tool outputs rather than LLM narration.
"""

import json
from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent


def _parse_tool_content(content: Any) -> Any:
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return content
    return content


async def run_tool_agent(
    *,
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    system_prompt: str,
    user_input: str,
    context_text: str | None = None,
) -> tuple[str, list[tuple[str, Any]]]:
    """Run a ReAct agent and return (final_text, tool_outputs).

    ``tool_outputs`` is a list of ``(tool_name, parsed_content)`` tuples, in the
    order the agent invoked them.
    """
    agent = create_react_agent(model, list(tools), prompt=system_prompt)
    human = user_input if not context_text else f"{context_text}\n\n{user_input}"
    result = await agent.ainvoke({"messages": [HumanMessage(content=human)]})

    tool_outputs: list[tuple[str, Any]] = []
    final_text = ""
    for msg in result.get("messages", []):
        if isinstance(msg, ToolMessage):
            tool_outputs.append((msg.name or "", _parse_tool_content(msg.content)))
        elif isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            # The final AI message after tool calls is the summary.
            final_text = msg.content if isinstance(msg.content, str) else str(msg.content)
    return final_text, tool_outputs
