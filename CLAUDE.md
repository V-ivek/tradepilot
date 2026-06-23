# tradepilot

## Overview

tradepilot is an open-source conversational AI trading assistant powered by
Alpaca's paper-trading API. Users ask questions in natural English about US
stocks — news, fundamentals, estimates, account, portfolio — and place paper
orders with a two-turn human-in-the-loop confirmation gate. Live trading is
architecturally blocked, not just disabled.

## Tech stack

- Python 3.11+ · FastAPI · LangGraph · `langchain-core`
- LiteLLM proxy for model routing
- `alpaca-py` for market data + paper trading
- PostgreSQL 16 · Redis 7 · Langfuse
- `structlog` · `pytest` · `ruff` · `uv` · Docker Compose

## Architecture

Two FastAPI services:

1. **App** (`src/`) — LangGraph agent graph:
   - Guard node (topic gate + ticker extraction)
   - Router
   - Specialist agent nodes: news, stock, finance, fundamentals, estimates, account
   - Trade agent + confirmation gate (two-turn LangGraph interrupt with HMAC token, 60s TTL)
   - Validator (PII strip, disclaimer injection, paper-mode enforcement)

2. **Gateway** (`gateway/`) — fronts external APIs:
   - `DataProvider` ABC with Alpaca primary + Finnhub/Alpha Vantage fallbacks
   - `PaperTradingService` Protocol with Alpaca-only adapter
   - Fails fast on startup if paper mode cannot be verified

Ports-and-adapters throughout; the graph only talks to the gateway over HTTP.

## Coding conventions

- DRY, TDD (failing test → minimal impl → green), explicit over implicit, async-first.
- One commit per task. Message format: `<type>: <short description>`
  (types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`).
- `ruff check` + `ruff format` clean before every commit.
- Keep prompts/responses US-markets, English-only in v1.

## Commands

```bash
uv sync --extra dev        # install / update deps
uv run pytest              # run tests
uv run pytest -m eval      # run LLM evals
uv run ruff check          # lint
uv run ruff format         # format
docker compose up          # full stack
docker compose -f docker-compose.minimal.yml up   # quickstart
```

## Port mappings

| Service   | Host port | Container port |
|-----------|-----------|----------------|
| app       | 4700      | 8000           |
| litellm   | 4701      | 4000           |
| langfuse  | 4702      | 3000           |
| postgres  | 4703      | 5432           |
| redis     | 4704      | 6379           |
| chat-ui   | 4705      | 8501           |
| gateway   | 4706      | 8000           |
