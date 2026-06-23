# Block types

The assistant's response is a list of blocks, streamed as SSE events.
`src/models/blocks.py` defines them as a Pydantic discriminated union.

| Block | Purpose | Required fields |
|---|---|---|
| `text` | Prose | `content` |
| `quote` | Latest quote | `symbol`, `price`, `change`, `change_pct` |
| `chart` | Price history | `symbol`, `timeframe`, `data` |
| `news_card` | One news article | `title`, `url`, `source`, `published_at` |
| `table` | Tabular data | `columns`, `rows` |
| `trade_intent` | Pending order (paper) | `symbol`, `side`, `qty`, `order_type`, `estimated_cost`, `confirmation_token`, `mode=paper` |
| `order_result` | Executed order (paper) | `order_id`, `status`, `filled_qty`, `timestamp`, `mode=paper` |
| `account_summary` | Account balances | `equity`, `cash`, `buying_power`, `mode=paper` |
| `positions_table` | Open positions | `rows`, `mode=paper` |

Trading blocks carry `mode: Literal["paper"]` non-optionally. The validator
drops any trading block that's missing the flag or carrying a different
value.
