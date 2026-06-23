# Paper-trading safety

Five independent layers enforce paper-only. Any one would be enough; stacked
they make bypass nearly impossible.

| Layer | What it checks | What it does on failure |
|---|---|---|
| Config | `ALPACA_PAPER_ONLY=true` at startup | Pydantic raises; app exits |
| Constructor | `TradingClient(paper=True)` | Alpaca SDK uses paper endpoint |
| `_assert_paper()` | `_base_url == PAPER_BASE_URL` before every I/O | Raises `RuntimeError`; request aborts |
| Startup | `get_account().mode == "paper"` | uvicorn exits |
| Validator | Every trading block has `mode="paper"` | Block is dropped from response |

## What the code blocks at compile-ish time

- There is no `LiveTradingAdapter` class.
- There is no config key that routes to a live endpoint.
- The live URL is a hardcoded denylist constant that `_assert_paper` rejects
  on every call.

## What the schema blocks at runtime

Every trading-related block uses `mode: Literal["paper"]`. A block missing
`mode`, or carrying any other value, fails Pydantic validation — it never
leaves the graph. Tests cover each block type.
