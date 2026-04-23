# Configuration

All configuration is environment variables. See `.env.example` for the full
list. Required:

| Variable | Description |
|---|---|
| `ALPACA_API_KEY_ID` | Paper-trading key ID. |
| `ALPACA_API_SECRET_KEY` | Paper-trading secret. |
| `ALPACA_PAPER_ONLY` | Must be `true`. Anything else is rejected at startup. |
| `ANTHROPIC_API_KEY` | Claude models. |
| `DATABASE_URL` | Postgres (checkpointer + futures). |
| `REDIS_URL` | Redis (semantic cache in the full stack). |
| `GATEWAY_URL` | Internal — app → gateway. |
| `JWT_SECRET` | App-signed tokens for the dev UI. Rotate in production. |

Optional:

| Variable | Default | Description |
|---|---|---|
| `FINNHUB_API_KEY` | — | Fallback for fundamentals / estimates. |
| `ALPHA_VANTAGE_API_KEY` | — | Fallback for symbol search. |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per-user sliding window. |
| `MAX_MESSAGE_LENGTH` | `2000` | Rejects longer messages. |
| `SEMANTIC_CACHE_ENABLED` | `true` | Turns the per-agent cache on/off. |
| `SEMANTIC_CACHE_STOCK_TTL` | `300` | Per-agent TTLs in seconds. |
| `SEMANTIC_CACHE_FINANCE_TTL` | `3600` | |
| `SEMANTIC_CACHE_FUNDAMENTALS_TTL` | `1800` | |
| `SEMANTIC_CACHE_ESTIMATES_TTL` | `900` | |
