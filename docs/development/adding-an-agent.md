# Adding an agent

1. **Prompt** — `src/agent/prompts/<your_agent>.py` exporting `SYSTEM_PROMPT`.
2. **Node** — `src/agent/nodes/<your_agent>.py` with an async
   `your_agent_node(state, *, model=None)` that calls tools and appends
   blocks to `state["blocks"]`.
3. **Tools** — place shared tools under `src/tools/<category>/`. Each tool
   file exports a private `_impl(gateway, …)` and a public `@tool`-decorated
   wrapper.
4. **Guard** — add your category to the guard prompt and to the
   `_category_to_node` mapping in `src/agent/nodes/guard.py`.
5. **Graph** — register the node in `DEFAULT_NODES` in `src/agent/graph.py`
   and wire it into the conditional edges from `guard` and to `validator`.
6. **Tests** — graph-level test that asserts routing + a node-level test
   with a stubbed `run_tool_agent`.

Follow the shape of `src/agent/nodes/news_agent.py` — it's the reference
implementation.
