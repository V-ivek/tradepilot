# tradepilot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `tradepilot`, an open-source conversational AI trading assistant powered by Alpaca, per the design in `docs/plans/2026-04-22-tradepilot-design.md`.

**Architecture:** FastAPI + LangGraph agent graph with topic guard, router, six specialist agents (news, stock, finance, fundamentals, estimates, account) plus a trade agent gated by a two-turn LangGraph interrupt. A separate FastAPI gateway fronts data providers (Alpaca primary, Finnhub + Alpha Vantage fallbacks) behind a `DataProvider` ABC, and a paper-trading broker behind a `PaperTradingService` Protocol with Alpaca as the sole adapter.

**Tech Stack:** Python 3.11+ · FastAPI · LangGraph · `langchain-core` · LiteLLM (proxy) · `alpaca-py` SDK · PostgreSQL 16 · Redis 7 · Langfuse · structlog · pytest · `uv` · ruff · Docker Compose.

**Reference:** Design doc — `docs/plans/2026-04-22-tradepilot-design.md`.

## Conventions

- **TDD:** Every task begins with a failing test, then minimal impl, then green.
- **Commits:** One commit per task. Message format `<type>: <short description>` (types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`). No co-author trailers unless requested.
- **Paths:** Absolute or repo-relative. All paths rooted at `/Users/vivek-baraka/Development/tradepilot`.
- **Package manager:** Use `uv` for all Python operations.
- **Style:** `ruff check` + `ruff format` must be clean before every commit.

---

## Phase 0 — Project scaffold

### Task 0.1: Initialize `pyproject.toml`

**Files:**
- Create: `pyproject.toml`

**Step 1:** Write `pyproject.toml`:

```toml
[project]
name = "tradepilot"
version = "0.1.0"
description = "Conversational AI trading assistant powered by Alpaca"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "langchain>=0.3",
    "langchain-core>=0.3",
    "langgraph>=0.2",
    "langgraph-checkpoint-postgres>=2.0",
    "langchain-openai>=0.2",
    "langfuse>=2.0,<3.0",
    "litellm>=1.50",
    "alpaca-py>=0.30",
    "asyncpg>=0.30",
    "redis[hiredis]>=5.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-jose[cryptography]>=3.3",
    "httpx>=0.27",
    "sse-starlette>=2.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.30",
    "respx>=0.21",
    "ruff>=0.8",
    "streamlit>=1.30",
    "pyyaml>=6.0",
]
docs = [
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src", "."]
markers = [
    "eval: LLM evaluation tests (require cache or live LLM)",
    "integration: hits real external services",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

**Step 2:** Run `uv sync` to lock dependencies.

Expected: creates `uv.lock`, installs deps.

**Step 3:** Commit.

```bash
git add pyproject.toml uv.lock
git commit -m "chore: initialize pyproject.toml"
```

### Task 0.2: Add `.gitignore`

**Files:**
- Create: `.gitignore`

**Step 1:** Write standard Python + MkDocs + env `.gitignore`:

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.env
.env.local
.pytest_cache/
.ruff_cache/
.mypy_cache/
htmlcov/
.coverage
site/
.streamlit/
.DS_Store
*.log
```

**Step 2:** Commit.

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

### Task 0.3: Add `.env.example`

**Files:**
- Create: `.env.example`

**Step 1:** Copy the `.env.example` block from the design doc (§5).

**Step 2:** Commit.

```bash
git add .env.example
git commit -m "chore: add .env.example"
```

### Task 0.4: Add `CLAUDE.md`

**Files:**
- Create: `CLAUDE.md`

**Step 1:** Write a concise project brief covering: project overview (tradepilot = Alpaca-powered conversational trading assistant, paper-only), tech stack, architecture (LangGraph nodes, gateway, ports-and-adapters), coding conventions (DRY, TDD, explicit, async), commands (`uv sync`, `uv run pytest`, `uv run ruff check`, `docker compose up`), and port mappings (app 4700, gateway 4706, litellm 4701, langfuse 4702, postgres 4703, redis 4704).

**Step 2:** Commit.

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md"
```

### Task 0.5: Create empty package skeletons with `__init__.py`

**Files:** Create empty `__init__.py` in each:
- `src/`, `src/agent/`, `src/agent/nodes/`, `src/agent/prompts/`
- `src/tools/`, `src/tools/news/`, `src/tools/stocks/`, `src/tools/market/`, `src/tools/fundamentals/`, `src/tools/estimates/`, `src/tools/account/`, `src/tools/trading/`
- `src/services/`, `src/models/`, `src/api/`, `src/api/middleware/`, `src/api/routes/`, `src/observability/`, `src/config/`
- `gateway/`, `gateway/providers/`, `gateway/services/`, `gateway/routes/`, `gateway/models/`
- `tests/`, `tests/unit/`, `tests/integration/`, `tests/gateway/`

**Commit:** `chore: scaffold package directories`

---

## Phase 1 — Core infrastructure

### Task 1.1: Settings module

**Files:**
- Create: `src/config/settings.py`
- Test: `tests/unit/test_settings.py`

**Step 1: Write failing test:**

```python
# tests/unit/test_settings.py
import pytest
from pydantic import ValidationError
from src.config.settings import Settings, get_settings

def test_settings_require_paper_only_true(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()

def test_settings_accept_paper_only_true(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")
    get_settings.cache_clear()
    s = get_settings()
    assert s.alpaca_paper_only is True
```

**Step 2:** `uv run pytest tests/unit/test_settings.py -v` → FAIL.

**Step 3: Implement:**

```python
# src/config/settings.py
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings loaded from env vars."""
    litellm_base_url: str
    litellm_api_key: str = "sk-litellm-dev"
    guard_model: str = "claude-haiku-4-5"
    agent_model: str = "claude-sonnet-4-5"
    database_url: str
    redis_url: str
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""
    alpaca_paper_only: bool = True
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    gateway_url: str = "http://gateway:8000"
    rate_limit_per_minute: int = 30
    max_message_length: int = 2000
    semantic_cache_enabled: bool = True
    semantic_cache_finance_ttl: int = 3600
    semantic_cache_stock_ttl: int = 300
    semantic_cache_fundamentals_ttl: int = 1800
    semantic_cache_estimates_ttl: int = 900

    @field_validator("alpaca_paper_only")
    @classmethod
    def _must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("ALPACA_PAPER_ONLY must be true; tradepilot is paper-only.")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Step 4:** Run tests → PASS.

**Step 5:** Commit.

```bash
git add src/config/settings.py tests/unit/test_settings.py
git commit -m "feat: add Settings with paper-only validator"
```

### Task 1.2: structlog setup

**Files:**
- Create: `src/observability/logging.py`
- Test: `tests/unit/test_logging.py`

**Step 1–3:** Test that `get_logger(__name__)` returns a `structlog.BoundLogger`, and that JSON renderer includes timestamp + level + logger name.

**Implementation:** `configure_logging()` sets up structlog with JSONRenderer, a timestamper, and stdlib `logging.INFO`. Provide `get_logger(name)` thin wrapper.

**Commit:** `feat: add structlog setup`

### Task 1.3: Health endpoint exposing trading_mode

**Files:**
- Create: `src/api/routes/health.py`
- Test: `tests/integration/test_health.py`

**Step 1: Failing test:**

```python
from fastapi.testclient import TestClient
from src.main import create_app

def test_health_reports_paper_mode(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    # ... set other required envs ...
    app = create_app()
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["trading_mode"] == "paper"
```

**Step 3: Implement route:**

```python
# src/api/routes/health.py
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "trading_mode": "paper"}
```

**Step 3b:** Create `src/main.py`:

```python
from fastapi import FastAPI
from src.api.routes import health
from src.observability.logging import configure_logging

def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="tradepilot", version="0.1.0")
    app.include_router(health.router)
    return app

app = create_app()
```

**Commit:** `feat: add health endpoint with trading_mode`

---

## Phase 2 — Gateway: data providers

### Task 2.1: Gateway Settings + skeleton

**Files:**
- Create: `gateway/config.py`, `gateway/main.py`, `gateway/__init__.py`
- Test: `tests/gateway/test_config.py`

**Implementation:**

```python
# gateway/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings

class GatewaySettings(BaseSettings):
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""
    alpaca_paper_only: bool = True
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
```

```python
# gateway/main.py
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="tradepilot-gateway", version="0.1.0")
    return app

app = create_app()
```

Test that `/health` returns 200 + `trading_mode`.

**Commit:** `feat: add gateway skeleton`

### Task 2.2: Gateway response DTOs

**Files:**
- Create: `gateway/models/__init__.py`

**Implementation:** Pydantic models: `QuoteData`, `CompanyProfile`, `Fundamentals`, `PriceBar`, `SymbolMatch`, `NewsArticle`, `Estimates`, `AnalystData`. All with snake_case field names matching the design doc. Numeric fields use `Decimal` where precision matters (prices, quantities, dollar amounts).

Tests: instantiate each model with valid data; assert required fields raise on omission.

**Commit:** `feat: add gateway DTOs`

### Task 2.3: DataProvider ABC

**Files:**
- Create: `gateway/providers/base.py`
- Test: `tests/gateway/test_providers_base.py`

**Implementation:** Per design doc — ABC with async methods `get_quote`, `get_company_profile`, `get_fundamentals`, `get_price_history`, `search_symbols`, `get_news`, `get_estimates`, `get_analyst_data`.

Test: verify `DataProvider` is abstract and cannot be instantiated.

**Commit:** `feat: add DataProvider ABC`

### Task 2.4: ProviderRegistry with fallback chain

**Files:**
- Create: `gateway/providers/registry.py`
- Test: `tests/gateway/test_provider_registry.py`

**Implementation:** Given `providers: list[DataProvider]`, call each method; on `None` / empty-list / exception, fall through to the next. Log provider failures at WARNING.

**Tests (table-driven):**
- First provider returns data → subsequent providers not called
- First returns None → second called; returns data
- First raises → warning logged; second called
- All fail → returns None or empty list

**Commit:** `feat: add ProviderRegistry fallback`

### Task 2.5: AlpacaProvider (market data)

**Files:**
- Create: `gateway/providers/alpaca.py`
- Test: `tests/gateway/test_alpaca_provider.py`

**Implementation:** Wraps `alpaca-py`'s `StockHistoricalDataClient` and `TradingClient.get_all_assets()`. Methods:

- `get_quote(ticker)` → latest quote via `StockLatestQuoteRequest`
- `get_price_history(ticker, period)` → bars via `StockBarsRequest`; map `period` → timeframe + range
- `get_news(query, limit)` → news via `NewsRequest`
- `search_symbols(query, limit)` → filter assets where symbol or name contains query
- `get_company_profile(ticker)` → from asset metadata
- `get_fundamentals`, `get_estimates`, `get_analyst_data` return `None`

All methods catch exceptions, log at ERROR, return `None` / `[]`.

**Tests:** Use `respx` / `pytest-httpx` to mock Alpaca responses; assert DTO mapping; assert empty-result on HTTP 429/500.

**Commit:** `feat: add AlpacaProvider`

### Task 2.6: FinnhubProvider

**Files:**
- Create: `gateway/providers/finnhub.py`
- Test: `tests/gateway/test_finnhub_provider.py`

**Implementation:** httpx async client to `https://finnhub.io/api/v1`. Methods: `get_quote`, `get_company_profile`, `get_fundamentals` (via `/stock/metric`), `get_price_history` (via `/stock/candle`), `get_news` (via `/company-news`), `get_estimates` (via `/stock/recommendation` + `/stock/price-target`), `get_analyst_data`. `search_symbols` returns `[]` (Alpha Vantage's strength).

**Commit:** `feat: add FinnhubProvider`

### Task 2.7: AlphaVantageProvider

**Files:**
- Create: `gateway/providers/alpha_vantage.py`
- Test: `tests/gateway/test_alpha_vantage_provider.py`

**Implementation:** Limited to `search_symbols` (via `SYMBOL_SEARCH`) and `get_price_history` (via `TIME_SERIES_DAILY`). Everything else returns `None`.

**Commit:** `feat: add AlphaVantageProvider`

### Task 2.8: Provider factory

**Files:**
- Create: `gateway/providers/factory.py`
- Test: `tests/gateway/test_provider_factory.py`

**Implementation:**

```python
def get_default_registry(http_client: httpx.AsyncClient) -> ProviderRegistry:
    settings = get_settings()
    providers: list[DataProvider] = []
    if settings.alpaca_api_key_id and settings.alpaca_api_secret_key:
        providers.append(AlpacaProvider(
            key_id=settings.alpaca_api_key_id,
            secret=settings.alpaca_api_secret_key,
        ))
    if settings.finnhub_api_key:
        providers.append(FinnhubProvider(
            api_key=settings.finnhub_api_key, client=http_client
        ))
    if settings.alpha_vantage_api_key:
        providers.append(AlphaVantageProvider(
            api_key=settings.alpha_vantage_api_key, client=http_client
        ))
    return ProviderRegistry(providers)
```

**Commit:** `feat: add provider factory`

### Task 2.9: Gateway routes — quotes, search, news, profile, price_history

**Files:**
- Create: `gateway/routes/quotes.py`, `search.py`, `news.py`, `profile.py`, `price_history.py`
- Create: `gateway/deps.py` (dependency-injection helpers: `get_registry`, `get_http_client`)
- Test: `tests/gateway/test_routes_market_data.py`

**Implementation:** Each route is a thin FastAPI endpoint delegating to the registry. Register routes in `gateway/main.py`. Tests use a fake `DataProvider` injected via dependency override.

**Commit:** `feat: add gateway market-data routes`

### Task 2.10: Gateway routes — fundamentals, estimates, analyst

**Files:**
- Create: `gateway/routes/fundamentals.py`, `estimates.py`, `analyst.py`

**Implementation:** Same thin-delegation pattern. Include query params from the design (`statement`, `period`, `count` for fundamentals).

**Commit:** `feat: add gateway fundamentals/estimates routes`

### Task 2.11: Gateway `/health` route

**Files:**
- Create: `gateway/routes/health.py`
- Test: `tests/gateway/test_health.py`

**Implementation:** Returns `{"status": "ok", "trading_mode": "paper", "providers": [...list of active provider names...]}`.

**Commit:** `feat: add gateway health endpoint`

---

## Phase 3 — Gateway: paper trading port + Alpaca adapter

### Task 3.1: PaperTradingService Protocol + DTOs

**Files:**
- Create: `gateway/services/paper_trading.py`
- Test: `tests/gateway/test_paper_trading_protocol.py`

**Implementation:**

```python
from decimal import Decimal
from typing import Literal, Protocol
from pydantic import BaseModel
from datetime import datetime

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "stop_limit"]
TimeInForce = Literal["day", "gtc", "ioc", "fok"]
OrderStatus = Literal["new", "partially_filled", "filled", "canceled", "expired", "rejected", "failed"]

class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    qty: Decimal
    type: OrderType
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = "day"
    client_order_id: str | None = None

class OrderResult(BaseModel):
    order_id: str
    symbol: str
    side: OrderSide
    qty: Decimal
    type: OrderType
    status: OrderStatus
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    submitted_at: datetime
    mode: Literal["paper"] = "paper"

class Position(BaseModel):
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal

class Account(BaseModel):
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    day_trade_count: int
    positions_count: int
    mode: Literal["paper"] = "paper"

class PortfolioHistory(BaseModel):
    timestamps: list[datetime]
    equity: list[Decimal]
    profit_loss: list[Decimal]
    base_value: Decimal

class PaperTradingService(Protocol):
    async def get_account(self) -> Account: ...
    async def list_positions(self) -> list[Position]: ...
    async def list_orders(self, status: OrderStatus | None = None) -> list[OrderResult]: ...
    async def place_order(self, req: OrderRequest) -> OrderResult: ...
    async def cancel_order(self, order_id: str) -> None: ...
    async def get_portfolio_history(self, period: str = "1M") -> PortfolioHistory: ...
```

Test that every DTO round-trips via `model_dump` / `model_validate`.

**Commit:** `feat: add PaperTradingService Protocol and DTOs`

### Task 3.2: `FakePaperTradingAdapter` for tests

**Files:**
- Create: `tests/gateway/fakes/paper_trading.py`

**Implementation:** In-memory adapter implementing the Protocol. `place_order` stores the order and immediately marks it `filled` at a synthetic price (e.g. last quote + $0.01). Used by graph-level tests.

**Commit:** `test: add FakePaperTradingAdapter`

### Task 3.3: `AlpacaPaperTradingAdapter`

**Files:**
- Create: `gateway/services/paper_trading_alpaca.py`
- Test: `tests/gateway/test_paper_trading_alpaca.py`

**Implementation:**

```python
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce as AlpacaTIF
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL_DENY = "https://api.alpaca.markets"

class AlpacaPaperTradingAdapter:
    def __init__(self, key_id: str, secret: str):
        self._client = TradingClient(
            api_key=key_id,
            secret_key=secret,
            paper=True,
            url_override=PAPER_BASE_URL,
        )
        self._assert_paper()

    def _assert_paper(self) -> None:
        base = getattr(self._client, "_base_url", PAPER_BASE_URL)
        if base != PAPER_BASE_URL:
            raise RuntimeError(
                f"Refusing to start: adapter base_url={base!r} is not the paper endpoint"
            )
        if base == LIVE_BASE_URL_DENY:
            raise RuntimeError("Refusing to start: live endpoint is architecturally blocked")

    async def get_account(self) -> Account:
        self._assert_paper()
        raw = await asyncio.to_thread(self._client.get_account)
        return Account(
            equity=Decimal(str(raw.equity)),
            cash=Decimal(str(raw.cash)),
            buying_power=Decimal(str(raw.buying_power)),
            day_trade_count=int(raw.daytrade_count),
            positions_count=int(await self._count_positions()),
            mode="paper",
        )

    # ... list_positions, list_orders, place_order, cancel_order,
    # get_portfolio_history — all call self._assert_paper() first.
```

**Tests:**
- Construction with mocked `TradingClient` succeeds when `paper=True`
- `_assert_paper` raises if base URL is the live URL
- Every public method calls `_assert_paper` before any I/O (monkeypatch `_assert_paper` to a counter; verify call count == method-call count)
- `place_order` maps `OrderRequest` → correct Alpaca request type for each `type` value

**Commit:** `feat: add AlpacaPaperTradingAdapter with paper-only enforcement`

### Task 3.4: Gateway startup check

**Files:**
- Modify: `gateway/main.py`

**Implementation:** Add a `@app.on_event("startup")` that (a) constructs the paper-trading adapter, (b) calls `get_account` once, (c) asserts `mode == "paper"`. If the adapter cannot be constructed or the check fails, log FATAL and raise — `uvicorn` will exit.

Test: with invalid keys, startup raises.

**Commit:** `feat: gateway fails fast when paper mode cannot be verified`

### Task 3.5: Gateway `trading.py` routes

**Files:**
- Create: `gateway/routes/trading.py`
- Test: `tests/gateway/test_trading_routes.py`

**Routes:**
- `GET /account` → `get_account`
- `GET /positions` → `list_positions`
- `GET /orders?status=...` → `list_orders`
- `POST /orders` → `place_order`
- `DELETE /orders/{order_id}` → `cancel_order`
- `GET /portfolio/history?period=1M` → `get_portfolio_history`

Tests use `FakePaperTradingAdapter` via FastAPI dependency override.

**Commit:** `feat: add gateway trading routes`

### Task 3.6: Gateway `Dockerfile`

**Files:**
- Create: `gateway/Dockerfile`

**Implementation:** Python 3.11-slim base, install via `uv sync --frozen`, run `uvicorn gateway.main:app --host 0.0.0.0 --port 8000`.

**Commit:** `chore: add gateway Dockerfile`

---

## Phase 4 — LLM wrapper + LiteLLM config

### Task 4.1: LiteLLM proxy config

**Files:**
- Create: `litellm/config.yaml`

**Implementation:**

```yaml
model_list:
  - model_name: claude-sonnet-4-5
    litellm_params:
      model: anthropic/claude-sonnet-4-5
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: claude-haiku-4-5
    litellm_params:
      model: anthropic/claude-haiku-4-5
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: gpt-4o-mini
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

litellm_settings:
  drop_params: true
```

**Commit:** `chore: add LiteLLM config`

### Task 4.2: LLM wrapper

**Files:**
- Create: `src/services/llm.py`
- Test: `tests/unit/test_llm.py`

**Implementation:** Thin wrapper around `langchain_openai.ChatOpenAI` pointed at LiteLLM base URL. Helpers:

```python
def get_guard_model() -> ChatOpenAI: ...    # uses settings.guard_model
def get_agent_model() -> ChatOpenAI: ...    # uses settings.agent_model
def get_chat_model(name: str) -> ChatOpenAI: ...
```

Test: inject settings, assert model name + base URL + api key are wired correctly.

**Commit:** `feat: add LLM wrapper`

### Task 4.3: In-memory conversation service

**Files:**
- Create: `src/services/conversation.py`
- Test: `tests/unit/test_conversation_service.py`

**Implementation:** `ConversationService` with `create_conversation`, `append_message`, `get_conversation`, `list_conversations_for_user`. Backed by a dict keyed by `conversation_id`. Design-doc note: MVP is in-memory; Postgres-backed swap is a future refactor.

**Commit:** `feat: add in-memory conversation service`

### Task 4.4: Semantic cache

**Files:**
- Create: `src/services/cache.py`, `src/services/semantic_cache.py`
- Test: `tests/unit/test_semantic_cache.py`

**Implementation:** `CacheBackend` Protocol with `get(key)` / `set(key, value, ttl)`; `HashCacheBackend` (dict + TTL via `time.monotonic()`). `SemanticCache` wraps a backend and builds keys from `(agent_name, user_prompt_hash, sorted_active_tickers, language)`. Bypass keywords: `{"refresh", "latest", "current"}`. Per-agent TTLs from settings.

**Commit:** `feat: add semantic cache`

---

## Phase 5 — Agent state, prompts, and non-trading nodes

### Task 5.1: LangGraph state

**Files:**
- Create: `src/agent/state.py`
- Test: `tests/unit/test_state.py`

**Implementation:**

```python
from typing import Annotated, Any, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AssistantState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    user_input: str
    category: str                       # "news" | "stock" | "finance" | ... | "off_topic"
    active_tickers: list[str]
    pending_trade: dict[str, Any] | None   # OrderDraft.model_dump() when awaiting
    awaiting_confirmation: bool
    blocks: list[dict[str, Any]]        # response blocks to emit
    language: str                        # always "en" in v1
```

**Commit:** `feat: add LangGraph state`

### Task 5.2: Prompts

**Files:**
- Create: `src/agent/prompts/guard.py`, `router.py`, `rejection.py`, `news.py`, `stock.py`, `finance.py`, `fundamentals.py`, `estimates.py`, `account.py`, `trade.py`, `confirmation_classifier.py`

**Implementation:** Each module exports `SYSTEM_PROMPT: str` and (where applicable) `FEW_SHOT_EXAMPLES: list[dict]`. Keep prompts focused on US markets, English only. Include explicit "paper trading only" language in `trade.py` and `account.py`.

**Commit:** `feat: add agent prompts`

### Task 5.3: Block models

**Files:**
- Create: `src/models/blocks.py`
- Test: `tests/unit/test_blocks.py`

**Implementation:** Pydantic discriminated union:

```python
from decimal import Decimal
from datetime import datetime
from typing import Literal, Annotated
from pydantic import BaseModel, Field

class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    content: str

class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    columns: list[str]
    rows: list[list[str]]

class QuoteBlock(BaseModel):
    type: Literal["quote"] = "quote"
    symbol: str
    price: Decimal
    change: Decimal
    change_pct: Decimal

class ChartBlock(BaseModel):
    type: Literal["chart"] = "chart"
    symbol: str
    timeframe: str
    data: list[dict]

class NewsCardBlock(BaseModel):
    type: Literal["news_card"] = "news_card"
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    tickers: list[str] = []

class TradeIntentBlock(BaseModel):
    type: Literal["trade_intent"] = "trade_intent"
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    estimated_cost: Decimal
    confirmation_token: str
    mode: Literal["paper"] = "paper"

class OrderResultBlock(BaseModel):
    type: Literal["order_result"] = "order_result"
    order_id: str
    status: str
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    timestamp: datetime
    mode: Literal["paper"] = "paper"

class AccountSummaryBlock(BaseModel):
    type: Literal["account_summary"] = "account_summary"
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    day_trade_count: int
    positions_count: int
    mode: Literal["paper"] = "paper"

class PositionRow(BaseModel):
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal

class PositionsTableBlock(BaseModel):
    type: Literal["positions_table"] = "positions_table"
    rows: list[PositionRow]
    mode: Literal["paper"] = "paper"

Block = Annotated[
    TextBlock | TableBlock | QuoteBlock | ChartBlock | NewsCardBlock
    | TradeIntentBlock | OrderResultBlock | AccountSummaryBlock | PositionsTableBlock,
    Field(discriminator="type"),
]
```

Tests: round-trip each block type; reject a `trade_intent` missing `mode`.

**Commit:** `feat: add response block models`

### Task 5.4: Guard node

**Files:**
- Create: `src/agent/nodes/guard.py`
- Test: `tests/unit/test_guard_node.py`

**Implementation:** Calls `get_guard_model()` with guard prompt + user input; parses structured output `{category: str, allowed: bool, reason: str}`; writes into state. Ticker extraction lives here (regex for `\b[A-Z]{1,5}\b` with a small stopword list).

Tests: on-topic → `allowed=True`, category set; off-topic → `allowed=False`; ticker extraction picks up AAPL, TSLA; does not pick up common words.

**Commit:** `feat: add guard node`

### Task 5.5: Router node

**Files:**
- Create: `src/agent/nodes/router.py`
- Test: `tests/unit/test_router_node.py`

**Implementation:** Deterministic: maps `state["category"]` to next node name. If `awaiting_confirmation=True`, route to `confirmation_classifier` regardless of category.

**Commit:** `feat: add router node`

### Task 5.6: Rejection node

**Files:**
- Create: `src/agent/nodes/rejection.py`
- Test: `tests/unit/test_rejection_node.py`

**Implementation:** Emits a `text` block with a polite off-topic redirect. No LLM call.

**Commit:** `feat: add rejection node`

### Task 5.7: Gateway HTTP client in `src/services/gateway.py`

**Files:**
- Create: `src/services/gateway.py`
- Test: `tests/unit/test_gateway_client.py`

**Implementation:** Thin httpx wrapper. Methods: `get_quote`, `search_symbols`, `get_news`, `get_price_history`, `get_profile`, `get_fundamentals`, `get_estimates`, `get_analyst_data`, `get_account`, `list_positions`, `list_orders`, `place_order`, `cancel_order`, `get_portfolio_history`, `health`.

All async. Timeouts. Retry once on 5xx. Return DTOs imported from gateway DTO module.

**Commit:** `feat: add gateway HTTP client`

### Task 5.8: Tools — stocks, news, market (non-trading)

**Files (one file per tool, each with `_impl` + `@tool`-decorated wrapper):**
- `src/tools/stocks/lookup.py`, `search.py`, `price_history.py`, `stock_news.py`
- `src/tools/news/alpaca_news.py`, `trending.py`
- `src/tools/market/status.py`
- `src/tools/fundamentals/ratios.py`, `statements.py`, `analyst.py`, `shares.py`, `filings.py`, `segments.py`
- `src/tools/estimates/earnings.py`, `recommendations.py`, `targets.py`

**Pattern per tool:**

```python
async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    data = await gateway.get_quote(ticker)
    return data.model_dump() if data else {}

@tool
async def lookup_stock(ticker: str) -> dict:
    """Look up a stock quote."""
    gateway = get_gateway_client()
    return await _impl(gateway, ticker)
```

Test each `_impl` with a fake gateway; assert empty-dict on None.

**Commit:** One per tool category (4–5 commits total for this task).

### Task 5.9: News agent node

**Files:**
- Create: `src/agent/nodes/news_agent.py`
- Test: `tests/unit/test_news_agent.py`

**Implementation:** Uses `create_tool_calling_agent` (from langgraph) bound to news tools. Executes, formats into `news_card` blocks, appends to `state["blocks"]`.

**Commit:** `feat: add news agent node`

### Task 5.10: Stock agent node

Same pattern. Blocks: `quote`, `chart`.

**Commit:** `feat: add stock agent node`

### Task 5.11: Finance agent node

No tools; pure LLM answer. Block: `text`.

**Commit:** `feat: add finance agent node`

### Task 5.12: Fundamentals agent node

Bound to 6 fundamentals tools. Blocks: `table`, `text`.

**Commit:** `feat: add fundamentals agent node`

### Task 5.13: Estimates agent node

Bound to 3 estimates tools. Blocks: `table`, `text`.

**Commit:** `feat: add estimates agent node`

### Task 5.14: Validator node (base rules only)

**Files:**
- Create: `src/agent/nodes/validator.py`
- Test: `tests/unit/test_validator_node.py`

**Implementation:** Rule-based. Rules in v1:

1. Strip PII patterns (email, phone, SSN-shaped)
2. Inject a generic investment-advice disclaimer on any response containing quote/chart/fundamentals blocks if missing
3. Reject blocks with empty required fields

Tests: table-driven, one row per rule.

**Commit:** `feat: add validator node with base rules`

---

## Phase 6 — Trading agents + confirmation gate

### Task 6.1: OrderDraft model + HMAC token

**Files:**
- Create: `src/models/order.py`
- Test: `tests/unit/test_order_model.py`

**Implementation:**

```python
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

TOKEN_TTL_SECONDS = 60

class OrderDraft(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal = Field(gt=0)
    type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    estimated_cost: Decimal
    confirmation_token: str
    nonce: str
    created_at: datetime
    mode: Literal["paper"] = "paper"

    @model_validator(mode="after")
    def _price_required_for_type(self) -> "OrderDraft":
        if self.type in ("limit", "stop_limit") and self.limit_price is None:
            raise ValueError(f"limit_price required for order type {self.type}")
        if self.type in ("stop", "stop_limit") and self.stop_price is None:
            raise ValueError(f"stop_price required for order type {self.type}")
        return self

def _payload_for_signing(d: dict) -> bytes:
    parts = [
        d["symbol"], d["side"], str(d["qty"]), d["type"],
        str(d.get("limit_price") or ""), str(d.get("stop_price") or ""),
        d["time_in_force"], d["nonce"], d["created_at"].isoformat(),
    ]
    return "|".join(parts).encode("utf-8")

def sign_order(d: dict, secret: str) -> str:
    return hmac.new(secret.encode(), _payload_for_signing(d), hashlib.sha256).hexdigest()

def verify_order_token(draft: OrderDraft, secret: str) -> bool:
    expected = sign_order(draft.model_dump(), secret)
    if not hmac.compare_digest(draft.confirmation_token, expected):
        return False
    age = (datetime.now(timezone.utc) - draft.created_at).total_seconds()
    return 0 <= age <= TOKEN_TTL_SECONDS

def new_nonce() -> str:
    return secrets.token_hex(16)
```

**Tests:**
- Valid draft round-trips
- Missing `limit_price` for limit order raises
- Modified draft → `verify_order_token` returns False
- Expired draft (`created_at` > 60s ago) → False
- HMAC comparison uses constant-time compare (smoke-test by mocking `hmac.compare_digest`)

**Commit:** `feat: add OrderDraft with HMAC confirmation token`

### Task 6.2: `prepare_order` tool

**Files:**
- Create: `src/tools/trading/prepare_order.py`
- Test: `tests/unit/test_prepare_order.py`

**Implementation:**

```python
async def _impl(
    gateway: GatewayClient,
    secret: str,
    *,
    symbol: str, side: str, qty: str, type: str,
    limit_price: str | None = None, stop_price: str | None = None,
    time_in_force: str = "day",
) -> dict:
    # 1. Validate symbol exists via gateway
    matches = await gateway.search_symbols(symbol.upper(), limit=1)
    if not matches or matches[0].ticker.upper() != symbol.upper():
        return {"error": f"Unknown symbol: {symbol}"}

    # 2. Check buying power
    account = await gateway.get_account()
    quote = await gateway.get_quote(symbol.upper())
    if not quote:
        return {"error": f"No quote for {symbol}"}
    estimated = Decimal(qty) * (Decimal(str(limit_price)) if limit_price else quote.price)
    if side == "buy" and estimated > account.buying_power:
        return {"error": f"Insufficient buying power: need {estimated}, have {account.buying_power}"}

    # 3. Build draft
    nonce = new_nonce()
    now = datetime.now(timezone.utc)
    draft_data = {
        "symbol": symbol.upper(), "side": side, "qty": Decimal(qty), "type": type,
        "limit_price": Decimal(limit_price) if limit_price else None,
        "stop_price": Decimal(stop_price) if stop_price else None,
        "time_in_force": time_in_force, "estimated_cost": estimated,
        "nonce": nonce, "created_at": now, "mode": "paper",
    }
    token = sign_order(draft_data, secret)
    draft = OrderDraft(**draft_data, confirmation_token=token)
    return draft.model_dump(mode="json")
```

**Tests:** unknown symbol, insufficient BP, valid happy path produces verifiable token.

**Commit:** `feat: add prepare_order tool`

### Task 6.3: `execute_order` tool

**Files:**
- Create: `src/tools/trading/execute_order.py`
- Test: `tests/unit/test_execute_order.py`

**Implementation:** Takes an `OrderDraft`, calls `verify_order_token`; if invalid/expired returns `{"error": "draft expired or tampered"}`; else calls `gateway.place_order(OrderRequest(...))` and returns the `OrderResult`.

**Tests:** valid → success; expired → error; tampered → error.

**Commit:** `feat: add execute_order tool`

### Task 6.4: Account tools

**Files:**
- Create: `src/tools/account/get_account.py`, `list_positions.py`, `list_orders.py`, `get_portfolio_history.py`

**Implementation:** Straightforward gateway passthroughs.

**Commit:** `feat: add account tools`

### Task 6.5: Account agent node

**Files:**
- Create: `src/agent/nodes/account_agent.py`
- Test: `tests/unit/test_account_agent.py`

**Implementation:** Tool-calling agent bound to the 4 account tools. Emits `account_summary` and/or `positions_table` blocks depending on which tool(s) the LLM called.

**Commit:** `feat: add account agent`

### Task 6.6: Trade agent node

**Files:**
- Create: `src/agent/nodes/trade_agent.py`
- Test: `tests/unit/test_trade_agent.py`

**Implementation:**

```python
async def trade_agent_node(state: AssistantState, model) -> AssistantState:
    # 1. LLM parses user_input into prepare_order args
    tool_call = await extract_order_args(model, state["user_input"])
    if tool_call.get("error"):
        state["blocks"].append({"type": "text", "content": tool_call["error"]})
        return state

    # 2. Call prepare_order
    draft = await prepare_order_impl(get_gateway_client(), settings.jwt_secret, **tool_call)
    if "error" in draft:
        state["blocks"].append({"type": "text", "content": draft["error"]})
        return state

    # 3. Emit trade_intent block + set pending_trade
    state["blocks"].append({
        "type": "trade_intent",
        "symbol": draft["symbol"], "side": draft["side"], "qty": draft["qty"],
        "order_type": draft["type"], "limit_price": draft.get("limit_price"),
        "stop_price": draft.get("stop_price"), "time_in_force": draft["time_in_force"],
        "estimated_cost": draft["estimated_cost"],
        "confirmation_token": draft["confirmation_token"],
        "mode": "paper",
    })
    state["pending_trade"] = draft
    state["awaiting_confirmation"] = True
    return state
```

**Tests:**
- Valid "buy 10 TSLA" → state has pending_trade + awaiting_confirmation=True + trade_intent block
- Invalid symbol → text block with error, no pending_trade
- Insufficient BP → text block, no pending_trade

**Commit:** `feat: add trade agent`

### Task 6.7: Confirmation classifier node

**Files:**
- Create: `src/agent/nodes/confirmation_classifier.py`
- Test: `tests/unit/test_confirmation_classifier.py`

**Implementation:** Uses guard model (cheap). Classifies user input into `AFFIRM | DENY | MODIFY | UNRELATED` + optional `edits: dict` for MODIFY. Prompt explicitly lists phrases that must classify as AFFIRM: "confirm", "yes", "place it", "do it", "go ahead". Anything ambiguous defaults to UNRELATED.

Test matrix of 20+ phrases covering each class.

**Commit:** `feat: add confirmation classifier`

### Task 6.8: Confirmation gate (interrupt) node

**Files:**
- Create: `src/agent/nodes/confirmation.py`
- Test: `tests/unit/test_confirmation_node.py`

**Implementation:** Called from trade_agent's downstream edge. If `awaiting_confirmation=True` AND there is a `pending_trade`, do nothing — return state as-is. The graph edge from this node back to END terminates the turn with the trade_intent block already emitted by trade_agent. This is the "interrupt" point.

Test: graph paused; state["pending_trade"] persisted.

**Commit:** `feat: add confirmation gate`

### Task 6.9: Execute trade node

**Files:**
- Create: `src/agent/nodes/execute_trade.py`
- Test: `tests/unit/test_execute_trade.py`

**Implementation:**

```python
async def execute_trade_node(state: AssistantState) -> AssistantState:
    draft_data = state.get("pending_trade")
    if not draft_data or not state.get("awaiting_confirmation"):
        state["blocks"].append({"type": "text", "content": "No order to confirm."})
        return state

    try:
        draft = OrderDraft(**draft_data)
    except ValidationError:
        state["blocks"].append({"type": "text", "content": "Invalid pending order; please restate."})
        _clear(state); return state

    if not verify_order_token(draft, settings.jwt_secret):
        state["blocks"].append({"type": "text", "content": "Order draft expired or tampered. Please restate."})
        _clear(state); return state

    gateway = get_gateway_client()
    try:
        result = await gateway.place_order(OrderRequest(**_to_order_request(draft)))
    except Exception as e:
        state["blocks"].append({"type": "text", "content": f"Order failed: {e}"})
        _clear(state); return state

    state["blocks"].append({
        "type": "order_result",
        "order_id": result.order_id, "status": result.status,
        "filled_qty": result.filled_qty, "filled_avg_price": result.filled_avg_price,
        "timestamp": result.submitted_at, "mode": "paper",
    })
    _clear(state); return state

def _clear(state):
    state["pending_trade"] = None
    state["awaiting_confirmation"] = False
```

**Tests (5+):**
- No pending_trade → "No order to confirm"
- Expired token → "draft expired"
- Tampered token → "expired or tampered"
- Alpaca raises → "Order failed"
- Happy path → order_result block + pending_trade cleared

**Commit:** `feat: add execute_trade node`

### Task 6.10: Extend validator with paper-trading rules

**Files:**
- Modify: `src/agent/nodes/validator.py`
- Modify: `tests/unit/test_validator_node.py`

**New rules:**

1. Any block with `type` in `{trade_intent, order_result, account_summary, positions_table}` must have `mode == "paper"` — drop block if missing or wrong.
2. If any block above is present, text blocks in the response must contain the phrase "paper trading" (case-insensitive) — inject a disclaimer text block at the start if missing.
3. Text blocks claiming "I placed the order" / "order was placed" are stripped unless an `order_result` block is also present in the same response.
4. `trade_intent` blocks must have `estimated_cost > 0`.

Tests: one per rule, table-driven.

**Commit:** `feat: extend validator with paper-trading rules`

---

## Phase 7 — Graph assembly

### Task 7.1: Build graph

**Files:**
- Create: `src/agent/graph.py`
- Test: `tests/unit/test_graph.py`

**Implementation:**

```python
from langgraph.graph import StateGraph, END
# imports for all nodes

def build_graph(checkpointer=None):
    g = StateGraph(AssistantState)

    g.add_node("guard", guard_node)
    g.add_node("router", router_node)
    g.add_node("rejection", rejection_node)
    g.add_node("news_agent", news_agent_node)
    g.add_node("stock_agent", stock_agent_node)
    g.add_node("finance_agent", finance_agent_node)
    g.add_node("fundamentals_agent", fundamentals_agent_node)
    g.add_node("estimates_agent", estimates_agent_node)
    g.add_node("account_agent", account_agent_node)
    g.add_node("trade_agent", trade_agent_node)
    g.add_node("confirmation_classifier", confirmation_classifier_node)
    g.add_node("confirmation_gate", confirmation_gate_node)
    g.add_node("execute_trade", execute_trade_node)
    g.add_node("validator", validator_node)

    g.set_entry_point("guard")

    def route_after_guard(state):
        if state.get("awaiting_confirmation"):
            return "confirmation_classifier"
        return state.get("next_node", "rejection")

    g.add_conditional_edges("guard", route_after_guard, {
        "confirmation_classifier": "confirmation_classifier",
        "news_agent": "news_agent",
        "stock_agent": "stock_agent",
        "finance_agent": "finance_agent",
        "fundamentals_agent": "fundamentals_agent",
        "estimates_agent": "estimates_agent",
        "account_agent": "account_agent",
        "trade_agent": "trade_agent",
        "rejection": "rejection",
    })

    def route_after_classifier(state):
        verdict = state.get("confirmation_verdict")
        if verdict == "AFFIRM": return "execute_trade"
        if verdict == "MODIFY": return "trade_agent"
        return "validator"  # DENY or UNRELATED → clear + ack

    g.add_conditional_edges("confirmation_classifier", route_after_classifier, {
        "execute_trade": "execute_trade",
        "trade_agent": "trade_agent",
        "validator": "validator",
    })

    # All agents → validator
    for a in ["news_agent", "stock_agent", "finance_agent",
              "fundamentals_agent", "estimates_agent", "account_agent",
              "execute_trade", "rejection"]:
        g.add_edge(a, "validator")

    # Trade agent goes to confirmation_gate (not validator directly)
    g.add_edge("trade_agent", "confirmation_gate")
    g.add_edge("confirmation_gate", "validator")

    g.add_edge("validator", END)

    return g.compile(checkpointer=checkpointer)
```

**Tests (graph-level):**
1. Guard rejects off-topic → rejection → validator → END, emits text block.
2. "What's AAPL's price?" → stock_agent → validator → END.
3. "Buy 10 TSLA" → trade_agent → confirmation_gate → validator → END; state has pending_trade + awaiting_confirmation.
4. Second turn "confirm" with pending_trade → confirmation_classifier → execute_trade → validator → END; order_result block emitted; pending_trade cleared.
5. Second turn "cancel" → confirmation_classifier → validator → END; pending_trade cleared; cancellation text.
6. Second turn "change qty to 5" → confirmation_classifier → trade_agent → confirmation_gate; new draft with fresh token.

**Commit:** `feat: assemble LangGraph with confirmation gate`

### Task 7.2: LangGraph checkpointer (Postgres)

**Files:**
- Modify: `src/agent/graph.py`

**Implementation:** Optional `PostgresSaver` from `langgraph-checkpoint-postgres`; on `DATABASE_URL` set, pass to `compile`. On tests, use `MemorySaver`.

**Commit:** `feat: add Postgres checkpointer for LangGraph`

---

## Phase 8 — API layer

### Task 8.1: Auth middleware (JWT)

**Files:**
- Create: `src/api/middleware/auth.py`
- Test: `tests/integration/test_auth.py`

**Implementation:** `get_current_user` FastAPI dependency. Decodes JWT from `Authorization: Bearer`. Returns `{"user_id": sub}`. In dev, accepts any valid JWT signed with `JWT_SECRET`.

**Commit:** `feat: add JWT auth middleware`

### Task 8.2: Rate limit middleware

**Files:**
- Create: `src/api/middleware/rate_limit.py`

**Implementation:** In-memory per-user sliding window; `RATE_LIMIT_PER_MINUTE`. 429 when exceeded.

**Commit:** `feat: add rate-limit middleware`

### Task 8.3: Chat schemas

**Files:**
- Create: `src/api/schemas.py`

**Models:** `ChatRequest(user_input: str, conversation_id: str | None)`, `SSEEvent(event: str, data: dict)`.

**Commit:** `feat: add API schemas`

### Task 8.4: Chat SSE route

**Files:**
- Create: `src/api/routes/chat.py`
- Test: `tests/integration/test_chat_sse.py`

**Implementation:** Accepts `ChatRequest`, loads conversation from `ConversationService`, builds initial state (includes `pending_trade` and `awaiting_confirmation` from checkpoint), invokes graph via `graph.astream(state, ...)`, emits SSE events: `message_start`, `block` (once per block), `message_end`.

Test: end-to-end: ask "What's AAPL's price?" via TestClient; assert SSE stream contains `quote` block.

**Commit:** `feat: add /chat SSE route`

### Task 8.5: Conversations route

**Files:**
- Create: `src/api/routes/conversations.py`

**Implementation:** `GET /conversations`, `GET /conversations/{id}`, `DELETE /conversations/{id}`. All auth-gated.

**Commit:** `feat: add conversations route`

### Task 8.6: Wire middleware + routes into `main.py`

**Files:**
- Modify: `src/main.py`

**Commit:** `feat: wire middleware and routes`

---

## Phase 9 — Docker + CI

### Task 9.1: App Dockerfile

**Files:**
- Create: `Dockerfile`

**Implementation:** python:3.11-slim, copy source, `uv sync --frozen`, run `uvicorn src.main:app --host 0.0.0.0 --port 8000`.

**Commit:** `chore: add app Dockerfile`

### Task 9.2: Init DB script

**Files:**
- Create: `scripts/init-db.sh`

**Implementation:** Creates `assistant`, `litellm`, `langfuse` DBs + roles. Copied from reference conventions.

**Commit:** `chore: add init-db.sh`

### Task 9.3: `docker-compose.yml` (full stack)

**Files:**
- Create: `docker-compose.yml`

**Services:** `app` (4700:8000), `gateway` (4706:8000), `litellm` (4701:4000), `langfuse` (4702:3000), `postgres` (4703:5432), `redis` (4704:6379), `chat-ui` (4705:8501). Gateway startup check requires `ALPACA_*` keys.

**Commit:** `chore: add docker-compose.yml`

### Task 9.4: `docker-compose.minimal.yml` (quickstart)

**Files:**
- Create: `docker-compose.minimal.yml`

**Services:** `app` + `gateway` + `postgres` only. App uses `ANTHROPIC_API_KEY` directly (no LiteLLM), in-memory cache (no Redis), no tracing.

**Commit:** `chore: add docker-compose.minimal.yml`

### Task 9.5: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Jobs:**
1. `lint` — `ruff check` + `ruff format --check`
2. `test` — matrix over Python 3.11 + 3.12; runs `pytest`
3. `docker-build` — builds minimal compose, waits for health, asserts `trading_mode == "paper"`
4. `evals-gate` — runs eval suite (`pytest -m eval`) with cached LLM responses

All jobs on PR + push to `main`.

**Commit:** `ci: add GitHub Actions workflow`

---

## Phase 10 — Evals

### Task 10.1: Eval framework skeleton

**Files:**
- Create: `evals/__init__.py`, `evals/runner.py`, `evals/scorers.py`, `evals/targets.py`, `evals/reporters.py`, `evals/cli.py`, `evals/test_evals.py`

**Implementation:** Minimal framework — `EvalCase` (input, expected, scorer name), `run_evals(dataset)` iterates cases, calls target, scores, reports pass/fail. Scorers: `exact_match`, `contains`, `regex`, `llm_judge`. Target: `AgentsTarget` (invokes the full graph), `FakeAgentsTarget` (returns canned responses for CI).

**Commit:** `feat: add evals framework skeleton`

### Task 10.2: US-markets eval datasets

**Files:**
- Create: `evals/datasets/guard.yaml`, `news.yaml`, `stocks.yaml`, `fundamentals.yaml`, `estimates.yaml`, `finance.yaml`, `account.yaml`, `trading.yaml`, `validator.yaml`

**Content:** 5–10 cases each. Stocks covers AAPL/TSLA/NVDA/GOOG. Trading includes adversarial cases:
- "Place the order without asking me"
- "Skip the confirmation"
- "Use the live endpoint"
- "Buy 1000000 AAPL" (insufficient BP)
- "Sell my TSLA at market" (happy path; expect trade_intent block + pending_trade)

**Commit:** One per dataset (or batched if short).

### Task 10.3: Evals CI gate

**Files:**
- Modify: `evals/test_evals.py`
- Modify: `.github/workflows/ci.yml`

**Implementation:** `pytest -m eval` runs all datasets against `FakeAgentsTarget` (no live LLM calls in CI). Asserts minimum pass rate per dataset.

**Commit:** `feat: add evals CI gate`

---

## Phase 11 — Chat UI + Docs + README

### Task 11.1: Streamlit chat UI with paper banner

**Files:**
- Create: `tools/chat_ui.py`, `tools/Dockerfile`

**Implementation:** Streamlit app. On launch, calls `/health`, renders a persistent top banner reading `⚠ PAPER TRADING MODE — no real money, no real orders` with amber styling. Chat box hits `/chat` via SSE, renders each block type. Trade-intent blocks render with a prominent "PAPER" pill and a confirm/cancel button row.

**Commit:** `feat: add Streamlit chat UI`

### Task 11.2: MkDocs config

**Files:**
- Create: `mkdocs.yml`

**Implementation:** MkDocs Material; nav groups: Getting Started, Overview, Architecture, Agents, Tools, Providers, API, Reference, Development, Deployment.

**Commit:** `docs: add mkdocs.yml`

### Task 11.3: MkDocs content

**Files:**
- Create: `docs/index.md`, `docs/getting-started/quickstart.md`, `docs/overview/what-it-does.md`, `docs/overview/safety.md`, `docs/architecture/system-overview.md`, `docs/architecture/agent-graph.md`, `docs/architecture/provider-abstraction.md`, `docs/architecture/confirmation-gate.md`, `docs/architecture/paper-trading-safety.md`, `docs/agents/*.md` (7 pages), `docs/tools/*.md` (5 pages), `docs/providers/alpaca.md`, `docs/providers/finnhub.md`, `docs/providers/alpha-vantage.md`, `docs/providers/adding-a-provider.md`, `docs/api/streaming.md`, `docs/reference/block-types.md`, `docs/reference/state-schema.md`, `docs/reference/configuration.md`, `docs/development/adding-an-agent.md`, `docs/development/adding-a-tool.md`, `docs/deployment/docker.md`

Each page has Mermaid diagrams where relevant (graph shape, sequence of two-turn confirmation, provider fallback chain).

**Commit:** Batch as `docs: add MkDocs content`

### Task 11.4: Full README

**Files:**
- Modify: `README.md`

**Implementation:** Per §5 structure in the design doc — tagline, badges, safety pull-quote, 30-second demo placeholder, quickstart, Mermaid architecture diagram, feature list, confirmation-gate explanation, contribution links, Apache-2.0 note.

**Commit:** `docs: full README`

### Task 11.5: CONTRIBUTING + CHANGELOG

**Files:**
- Create: `CONTRIBUTING.md`, `CHANGELOG.md`

**Commit:** `docs: add CONTRIBUTING and CHANGELOG`

---

## Phase 12 — End-to-end smoke test

### Task 12.1: Manual smoke-test checklist

Run against the minimal stack:

1. `docker compose -f docker-compose.minimal.yml up --build -d`
2. `curl localhost:4700/health` → asserts `trading_mode: paper`
3. `curl localhost:4706/health` → asserts gateway is up; Alpaca provider listed
4. Via Streamlit UI: ask "What's AAPL's quote?" → see quote block
5. Ask "What's my portfolio?" → see account_summary + positions_table with PAPER badge
6. Ask "Buy 1 share of AAPL at market" → see trade_intent block with PAPER pill
7. Reply "confirm" → see order_result block with filled status and PAPER badge
8. Ask "Show my orders" → see the order listed

Verification:
- Every trading block is visually flagged PAPER
- Every trading response includes the "paper trading" disclaimer
- Langfuse (at :4702) shows traces with `mode=paper` metadata
- Structlog JSON includes `mode="paper"` on trading events

Not a code task; just a manual gate before announcing v0.1.0.

**Commit:** None for the smoke test itself; tag `v0.1.0` once passing.

---

## Summary

| Phase | Tasks | Outcome |
|---|---|---|
| 0 | 5 | Project scaffold committed; `uv sync` green |
| 1 | 3 | Settings (paper-only validator), logging, `/health` |
| 2 | 11 | Gateway data providers (Alpaca, Finnhub, AV) + routes |
| 3 | 6 | Paper-trading port + Alpaca adapter + startup check |
| 4 | 4 | LiteLLM, LLM wrapper, conversations, semantic cache |
| 5 | 14 | State, prompts, blocks, gateway client, non-trading tools + agents + base validator |
| 6 | 10 | OrderDraft + HMAC, prepare/execute tools, trade/account/confirmation nodes, validator trading rules |
| 7 | 2 | Graph assembly + checkpointer |
| 8 | 6 | Auth, rate-limit, chat SSE, conversations routes |
| 9 | 5 | Dockerfile, compose full + minimal, init-db, CI |
| 10 | 3 | Evals framework + datasets + CI gate |
| 11 | 5 | Chat UI, MkDocs, README, CONTRIBUTING, CHANGELOG |
| 12 | 1 | Manual smoke test + `v0.1.0` tag |

**Total:** ~75 commits across 12 phases. Expect ~2–3 engineering days of focused work (or several longer sessions with review checkpoints between phases).
