# State schema

`src/agent/state.py` defines `AssistantState`, the `TypedDict` every node
reads from and writes to.

| Key | Type | Set by | Consumed by |
|---|---|---|---|
| `messages` | list[BaseMessage] | LangGraph | every node |
| `user_id` | str | chat route | account + trading paths |
| `conversation_id` | str | chat route | checkpointer |
| `user_input` | str | chat route | every agent |
| `category` | str | guard | router |
| `next_node` | str | guard / router | conditional edges |
| `active_tickers` | list[str] | guard | every agent |
| `pending_trade` | dict | trade_agent | confirmation classifier / execute_trade |
| `awaiting_confirmation` | bool | trade_agent | classifier / execute_trade |
| `confirmation_verdict` | str | classifier | conditional edge after classifier |
| `blocks` | list[dict] | every node | validator / chat route |
| `language` | str | chat route | agents (currently "en" only) |
