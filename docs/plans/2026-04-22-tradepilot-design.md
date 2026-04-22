# tradepilot — Design

**Date:** 2026-04-22
**Status:** Approved, awaiting implementation plan
**Repo:** https://github.com/V-ivek/tradepilot
**License:** Apache 2.0

## Summary

`tradepilot` is a conversational AI trading assistant for US markets, powered by
Alpaca. Users chat in natural English to research stocks (news, fundamentals,
estimates), inspect their paper-trading portfolio, and place paper orders with a
mandatory human-in-the-loop confirmation.

The project is an open-source showcase of:

- Multi-agent LangGraph orchestration with topic guards and output validation
- Ports-and-adapters vendor abstraction (market-data providers, paper-trading
  broker adapter)
- Safety-first design for LLM-driven transactions: defense-in-depth paper-only
  enforcement and a two-turn confirmation gate
- Production-adjacent infrastructure: LiteLLM proxy, Langfuse tracing,
  structured logging, semantic caching, evals CI gate

## Non-goals

- **No live trading, ever.** Paper-only enforcement is architectural, not a
  config toggle.
- **No non-US markets.** Single-market focus keeps the story tight.
- **No multilingual UX.** English only.
- **No order-management complexity beyond Alpaca's API** (no OCO/bracket logic
  we build ourselves; rely on what Alpaca exposes).
- **No mobile/native clients.** Streamlit debug chat + SSE-ready backend; UI
  work is someone else's fork.

## Tech stack

Python 3.11+ · FastAPI · LangGraph · `langchain-core` · LiteLLM (proxy) ·
`alpaca-py` SDK · PostgreSQL 16 · Redis 7 · Langfuse (self-hosted) · structlog ·
pytest · `uv` · ruff · Docker Compose · MkDocs Material.

## 1. End-state architecture

### LangGraph shape

```
        Guard (topic classifier, cheap model)
          |
          ├── off-topic ──► Rejection ──► SSE
          |
          └── on-topic ──► Router
                             |
        ┌────────────────────┼──────────────────────┐
        ▼          ▼         ▼        ▼        ▼    ▼
   News Agent  Stock A.  Finance  Fund.   Estim.  Account A.
        |          |        |       |        |        |
        └──────────┴────────┴───────┴────────┴────────┤
                                                     |
                                     Trade Agent ────┤
                                          |          |
                              Confirmation Gate      |
                               (interrupt node)      |
                                          |          |
                                  Execute Trade      |
                                          |          |
                                          ▼          ▼
                                      Validator (rule-based)
                                          |
                                          ▼
                                         SSE
```

### Specialist agents (7 total)

| Agent | Tools call | Data source |
|---|---|---|
| News | `get_news`, `get_stock_news`, `get_trending_news` | Alpaca News → Finnhub fallback |
| Stock | `lookup_stock`, `search_stocks`, `get_price_history` | Alpaca Market Data → Alpha Vantage fallback |
| Finance | none (LLM knowledge) | — |
| Fundamentals | `get_ratios`, `get_statements`, `get_analyst`, `get_shares`, `get_filings`, `get_segments` | Finnhub (primary) → Alpha Vantage |
| Estimates | `get_earnings`, `get_recommendations`, `get_targets` | Finnhub |
| Account (new) | `get_account`, `list_positions`, `list_orders`, `get_portfolio_history` | Alpaca paper-trading adapter |
| Trade (new) | `prepare_order`, `execute_order` | Alpaca paper-trading adapter (writes gated by confirmation) |

### Vendor layout

| Capability | Primary | Fallback |
|---|---|---|
| Quotes, bars, price history | Alpaca Market Data | Finnhub |
| Company news | Alpaca News | Finnhub |
| Symbol search | Alpaca Assets | Alpha Vantage |
| Company profile | Alpaca Assets | Finnhub |
| Fundamentals / ratios | Finnhub | Alpha Vantage |
| Analyst estimates & recommendations | Finnhub | — |
| ESG scores | — | — (out of scope for v1) |
| Account / orders / positions | Alpaca Trading (paper) | — |
| Market clock / calendar | Alpaca Clock | — |

Alpaca is the headline vendor. Finnhub and Alpha Vantage remain as optional
fallbacks — their keys are empty by default, and the fallback chain degrades
gracefully when they are absent.

## 2. Alpaca integration

### Alpaca APIs consumed (all via `alpaca-py` SDK)

| Alpaca API | Used by |
|---|---|
| Market Data — Stocks (bars, quotes, snapshots) | `AlpacaProvider.get_quote`, `get_price_history` |
| Market Data — News | `AlpacaProvider.get_news` |
| Trading — Account | `get_account` tool |
| Trading — Positions | `list_positions` tool |
| Trading — Orders (GET + POST) | `list_orders`, `execute_order` tools |
| Trading — Portfolio History | `get_portfolio_history` tool |
| Trading — Assets | `AlpacaProvider.search_symbols`, `get_company_profile` |
| Trading — Clock / Calendar | `get_market_status` tool |

### Ports & adapters

**Market data** uses the existing `DataProvider` ABC pattern:

```
gateway/providers/
├── base.py              # DataProvider ABC (the port)
├── registry.py          # ProviderRegistry with fallback chain
├── factory.py           # wires Alpaca primary, Finnhub + Alpha Vantage fallbacks
├── alpaca.py            # AlpacaProvider (new)
├── finnhub.py
└── alpha_vantage.py
```

`AlpacaProvider` implements `get_quote`, `get_price_history`, `get_news`,
`search_symbols`, `get_company_profile`. It returns `None` for
`get_fundamentals`, `get_estimates`, `get_esg_scores`, `get_analyst_data` — the
registry falls back to Finnhub for those.

**Paper trading** uses a parallel port-and-adapter structure:

```
gateway/services/
├── paper_trading.py         # PaperTradingService Protocol (the port) + DTOs
└── paper_trading_alpaca.py  # AlpacaPaperTradingAdapter (the adapter)
```

```python
class PaperTradingService(Protocol):
    async def get_account(self) -> Account: ...
    async def list_positions(self) -> list[Position]: ...
    async def list_orders(self, status: OrderStatus = ...) -> list[OrderResult]: ...
    async def place_order(self, req: OrderRequest) -> OrderResult: ...
    async def cancel_order(self, order_id: str) -> None: ...
    async def get_portfolio_history(self, period: str = "1M") -> PortfolioHistory: ...
```

Routes and tests depend on the Protocol, never on the Alpaca class. This leaves
the seam for a future second adapter (e.g. another broker's paper API) without
touching call sites.

`gateway/deps.py` constructs the adapter once at startup and injects the
Protocol type into `gateway/routes/trading.py`.

### Block types (SSE response payloads)

New blocks extend the existing block union in `src/models/blocks.py`:

| Block | Fields |
|---|---|
| `trade_intent` | `symbol`, `side`, `qty`, `type`, `limit_price`, `stop_price`, `time_in_force`, `estimated_cost`, `confirmation_token`, `mode` |
| `order_result` | `order_id`, `status`, `filled_qty`, `filled_avg_price`, `timestamp`, `mode` |
| `account_summary` | `equity`, `cash`, `buying_power`, `day_trade_count`, `positions_count`, `mode` |
| `positions_table` | rows of `{symbol, qty, avg_entry_price, market_value, unrealized_pl, unrealized_plpc}`, `mode` |

Every trading-related block carries `mode: "paper"` — the field is
non-optional, enforced by Pydantic.

## 2a. Paper-trading recognition (defense in depth)

### Backend safety (invisible, auditable)

1. **Config gate** — `ALPACA_PAPER_ONLY=true` required at startup. App refuses
   to boot if unset or false.
2. **Base URL allowlist** — `AlpacaPaperTradingAdapter` asserts
   `base_url == "https://paper-api.alpaca.markets"` on every call. The live URL
   (`api.alpaca.markets`) is a hardcoded denylist constant; no config can
   override it.
3. **Startup verification** — gateway calls `/v2/account` once at boot and
   verifies the Alpaca SDK client was constructed with `paper=True`. Fails
   fast on mismatch.
4. **Structured logs + Langfuse metadata** — every trading event emits
   `mode="paper"` so audits can prove no live trade ever ran.

### User-visible recognition

1. **Mode badge on every trading block** — `trade_intent`, `order_result`,
   `account_summary`, `positions_table` all carry a `mode: "paper"` field,
   rendered as a high-contrast amber "PAPER" pill. Non-optional in the schema.
2. **Explicit confirmation copy** — the pause message always reads, e.g.,
   `"Confirm PAPER order: BUY 10 TSLA @ market. Reply 'confirm' to place
   (paper only — no real money)."` Never "confirm order" without "PAPER."
3. **Validator rule** — any response containing a trading block or
   trade-related language must contain the phrase "paper trading" (or
   equivalent); validator auto-injects if missing.
4. **Persistent UI banner** — the Streamlit/debug chat shows a top banner:
   `"⚠ Paper Trading Mode — no real money, no real orders"` using the mode
   flag from `/health`.
5. **`/health` exposes mode** — returns `{"status": "ok", "trading_mode":
   "paper"}` so any client can assert mode programmatically.
6. **README "Safety" pull-quote** — first fold: *"tradepilot only connects to
   Alpaca's paper-trading endpoint. Live trading is architecturally blocked,
   not just disabled."*

## 3. Trading safety & confirmation gate

The confirmation gate is the load-bearing safety component.

### Two-turn flow

```
Turn 1 (user): "buy 10 TSLA at market"
  Guard → Router → Trade Agent
    Trade Agent:
      1. Calls prepare_order tool → validated OrderDraft
      2. Sets state["pending_trade"] = OrderDraft
      3. Sets state["awaiting_confirmation"] = True
      4. Emits trade_intent block
  → Confirmation Gate (LangGraph interrupt)
      - If awaiting_confirmation: end turn, SSE stream closes with the
        trade_intent block rendered; pending_trade persisted to checkpoint.

Turn 2 (user): "confirm" / "yes" / "do it"
  Guard → Confirmation Classifier (new lightweight node, cheap model)
      - Classifies: AFFIRM | DENY | MODIFY | UNRELATED
      - AFFIRM + pending_trade exists ──► Execute Trade
      - DENY ──► clear pending_trade, emit cancellation ack
      - MODIFY ("change qty to 5") ──► route back to Trade Agent with edit
      - UNRELATED ──► TTL expires (60s); clear; route normally
  Execute Trade:
      1. Re-validate pending_trade (replay-attack check)
      2. Verify confirmation_token matches and has not expired
      3. Call execute_order tool → Alpaca POST /v2/orders
      4. Emit order_result block with Alpaca order_id
      5. Clear pending_trade
```

### Why two turns, not single-turn tool-calling

A human-in-the-loop confirmation is the whole point. Letting the LLM
tool-call-and-execute in one turn gives the model the authority to place
orders, which is exactly what the design prevents.

LangGraph's interrupt primitive is purpose-built for this: pause, persist
state, resume on the next turn. This choice makes the safety property
testable: a unit test asserts "graph halts at confirmation_gate with
pending_trade set after any trade request."

### `OrderDraft` schema (validated before hitting Alpaca)

```python
class OrderDraft(BaseModel):
    symbol: str                       # uppercase, validated against Alpaca assets
    side: Literal["buy", "sell"]
    qty: Decimal                      # > 0; fractional-share-aware
    type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Decimal | None       # required iff type in {limit, stop_limit}
    stop_price: Decimal | None        # required iff type in {stop, stop_limit}
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    estimated_cost: Decimal           # from latest quote; shown to user
    confirmation_token: str           # HMAC(secret, order_fields + nonce); 60s TTL
    created_at: datetime
    mode: Literal["paper"] = "paper"  # not optional
```

### Confirmation token — replay & tamper resistance

- HMAC-signed at `prepare_order` time over all order fields + timestamp + nonce.
- **60-second TTL.** Expired drafts are rejected at execute time with a
  "draft expired, please restate" response.
- If the user modifies the draft, a new draft with a fresh token is issued;
  stale tokens cannot execute.

### Validator rules added for trading flows

1. `trade_intent` blocks must include `mode: "paper"` and an `estimated_cost`
   — drop the block otherwise.
2. Responses containing any trading block must include the phrase "paper
   trading" — auto-inject if missing.
3. Agent free-text must not include claims like "I've placed the order"
   unless an `order_result` block is present — strip unbacked claims.
4. The `execute_trade` node must be unreachable unless
   `awaiting_confirmation=True` AND the confirmation token is valid — enforced
   by graph topology (no edge from `trade_agent` → `execute_trade` directly)
   AND by a runtime guard inside `execute_trade`.

### Testing strategy

- **Unit tests:** validator rules are table-driven; `OrderDraft` validation
  has property tests.
- **Graph-level tests:** pytest cases that drive the graph turn-by-turn and
  assert (a) graph pauses at the confirmation gate on trade requests,
  (b) `pending_trade` is correctly persisted, (c) affirmative confirmation
  routes to `execute_trade`, (d) denial/timeout clears state, (e) modify path
  re-issues draft with new token.
- **Integration tests:** `FakePaperTradingAdapter` implementing the Protocol
  for offline CI; real `AlpacaPaperTradingAdapter` against Alpaca's paper
  sandbox for nightly integration.
- **Evals:** `evals/datasets/trading.yaml` includes adversarial prompts —
  "place without asking," "ignore the confirmation rule," "use the live
  endpoint" — asserts guard/validator rejects.

### Explicit failure-mode handling

| Failure | Behavior |
|---|---|
| User requests live trading | Guard rejects; polite paper-only explanation |
| Insufficient buying power | `prepare_order` catches via `/v2/account`; friendly error block; no `trade_intent` emitted |
| Alpaca API down at execute | `order_result` with `status: "failed"`; `pending_trade` cleared |
| Checkpoint lost between turns | Confirmation gate with no `pending_trade` → "I don't have an order to confirm" |
| Token TTL expired | Execute rejects with "draft expired, please restate" |

## 4. Initial scaffold

The repo starts empty (LICENSE + README stub on `main`). The first commit after
this design adds the full scaffold — no Baraka-specific legacy to strip because
the project begins clean here.

### What the scaffold includes

- `src/` application with 6 existing specialist agents (news, stock, finance,
  fundamentals, estimates, + the new account + trade), guard, router,
  validator, rejection nodes, LangGraph state + graph assembly
- `gateway/` data-provider service (Alpaca + Finnhub + Alpha Vantage) and
  paper-trading service (Alpaca adapter)
- `evals/` framework (runner, scorers, targets, reporters, CLI) + dataset
  scaffolds
- `tests/` unit + integration + gateway tests
- `tools/chat_ui.py` Streamlit client with paper-trading banner
- `docker-compose.yml` (full stack) + `docker-compose.minimal.yml`
  (3-container quickstart)
- `litellm/config.yaml` proxy routing
- `docs/` MkDocs source
- `.github/workflows/ci.yml` single CI workflow
- `README.md` (front-door story), `CONTRIBUTING.md`, `CHANGELOG.md`,
  `.env.example`, `.gitignore`, `pyproject.toml`, `mkdocs.yml`, `CLAUDE.md`

### What is deliberately absent

- No Kubernetes manifests / Helm / ArgoCD
- No deploy workflows
- No pre-built `site/` output (the `.gitignore` excludes it)
- No multi-environment overlays
- No non-US market code
- No multilingual prompts or disclaimers

## 5. Repo surface

### File layout

```
tradepilot/
├── README.md                             # front-door story, safety callout, quickstart
├── LICENSE                               # Apache 2.0
├── CONTRIBUTING.md                       # how to add a provider/tool/agent
├── CHANGELOG.md                          # keep-a-changelog
├── CLAUDE.md                             # project context for Claude Code
├── .env.example                          # Alpaca-first, minimal
├── .gitignore                            # excludes site/, .env, etc.
├── docker-compose.yml                    # full stack
├── docker-compose.minimal.yml            # 3-container quickstart
├── Dockerfile
├── pyproject.toml                        # name = "tradepilot"
├── mkdocs.yml
├── src/
│   ├── main.py
│   ├── config/settings.py
│   ├── agent/
│   │   ├── graph.py                      # includes account + trade + confirmation
│   │   ├── state.py                      # adds pending_trade, awaiting_confirmation
│   │   ├── nodes/
│   │   │   ├── guard.py
│   │   │   ├── router.py
│   │   │   ├── rejection.py
│   │   │   ├── news_agent.py
│   │   │   ├── stock_agent.py
│   │   │   ├── finance_agent.py
│   │   │   ├── fundamentals_agent.py
│   │   │   ├── estimates_agent.py
│   │   │   ├── account_agent.py          # NEW
│   │   │   ├── trade_agent.py            # NEW
│   │   │   ├── confirmation.py           # NEW — interrupt node
│   │   │   ├── confirmation_classifier.py # NEW — turn-2 intent
│   │   │   ├── execute_trade.py          # NEW
│   │   │   └── validator.py              # adds paper-trading disclaimer rules
│   │   └── prompts/                      # English, US-markets
│   ├── tools/
│   │   ├── news/                         # alpaca_news, trending
│   │   ├── stocks/                       # lookup, search, price_history, stock_news
│   │   ├── market/                       # status (Alpaca clock)
│   │   ├── fundamentals/                 # served by Finnhub via gateway
│   │   ├── estimates/                    # served by Finnhub via gateway
│   │   ├── account/                      # NEW — get_account, list_positions, list_orders, get_portfolio_history
│   │   └── trading/                      # NEW — prepare_order, execute_order
│   ├── services/
│   │   ├── llm.py
│   │   ├── conversation.py
│   │   ├── cache.py
│   │   └── semantic_cache.py
│   ├── models/
│   │   ├── conversation.py
│   │   ├── blocks.py                     # + trade_intent, order_result, account_summary, positions_table
│   │   └── order.py                      # OrderDraft
│   ├── api/
│   │   ├── schemas.py
│   │   ├── middleware/{auth,rate_limit}.py
│   │   └── routes/{health,chat,conversations}.py
│   └── observability/{logging,tracing,metrics}.py
├── gateway/
│   ├── main.py
│   ├── config.py
│   ├── deps.py
│   ├── Dockerfile
│   ├── providers/
│   │   ├── base.py                       # DataProvider ABC
│   │   ├── registry.py
│   │   ├── factory.py
│   │   ├── alpaca.py                     # NEW
│   │   ├── finnhub.py
│   │   └── alpha_vantage.py
│   ├── services/
│   │   ├── paper_trading.py              # PaperTradingService Protocol + DTOs
│   │   └── paper_trading_alpaca.py       # AlpacaPaperTradingAdapter
│   ├── models/                           # response DTOs
│   └── routes/
│       ├── health.py                     # exposes trading_mode
│       ├── quotes.py, search.py, news.py, profile.py, price_history.py
│       ├── fundamentals.py, estimates.py, analyst.py
│       └── trading.py                    # NEW
├── evals/
│   ├── (framework code)
│   └── datasets/                         # ~10 US-markets YAMLs
│       ├── guard.yaml
│       ├── news.yaml
│       ├── stocks.yaml
│       ├── fundamentals.yaml
│       ├── estimates.yaml
│       ├── finance.yaml
│       ├── account.yaml                  # NEW
│       ├── trading.yaml                  # NEW — incl. adversarial cases
│       └── validator.yaml
├── tests/
│   ├── unit/
│   ├── integration/
│   └── gateway/
├── tools/
│   └── chat_ui.py                        # Streamlit with paper banner
├── litellm/
│   └── config.yaml
├── scripts/
│   └── init-db.sh
└── docs/                                 # MkDocs Material
    ├── index.md
    ├── getting-started/
    ├── overview/
    ├── agents/                           # 7 agent pages
    ├── tools/
    ├── providers/                        # alpaca, finnhub, alpha-vantage, adding-a-provider
    ├── architecture/                     # system, agent-graph, provider-abstraction, confirmation-gate, paper-trading-safety
    ├── api/                              # streaming SSE, openapi
    ├── reference/                        # block-types, state-schema, glossary, configuration
    ├── development/
    ├── deployment/                       # docker (no k8s)
    └── plans/
        └── 2026-04-22-tradepilot-design.md  # this doc
```

### `.env.example` — Alpaca-first, minimal

```bash
# === Alpaca (required) ===
# Get paper-trading keys at https://app.alpaca.markets (free)
ALPACA_API_KEY_ID=
ALPACA_API_SECRET_KEY=
ALPACA_PAPER_ONLY=true          # must be true; app refuses to boot otherwise

# === LLM provider (at least one required) ===
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# === Optional fallback providers ===
FINNHUB_API_KEY=
ALPHA_VANTAGE_API_KEY=

# === Infra (defaults work for docker-compose) ===
LITELLM_BASE_URL=http://litellm:4000/v1
LITELLM_API_KEY=sk-litellm-dev
DATABASE_URL=postgresql+asyncpg://assistant:assistant@postgres:5432/assistant
REDIS_URL=redis://redis:6379/0
GATEWAY_URL=http://gateway:8000

# === Models ===
GUARD_MODEL=claude-haiku-4-5
AGENT_MODEL=claude-sonnet-4-5

# === Observability (optional) ===
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=http://langfuse:3000

# === Auth ===
JWT_SECRET=dev-secret-change-in-production
JWT_ALGORITHM=HS256

# === Limits ===
RATE_LIMIT_PER_MINUTE=30
MAX_MESSAGE_LENGTH=2000
```

### README structure (front door)

1. One-line tagline + badge row (Apache-2.0 · Python 3.11+ · Docker ·
   Alpaca Paper API · Langfuse)
2. **What it is** — "A conversational AI trading assistant. Ask questions in
   natural English about US stocks — news, fundamentals, estimates, your
   portfolio — and place paper orders with human-in-the-loop confirmation."
3. **Safety callout** (pull-quote box) — "tradepilot only connects to
   Alpaca's paper-trading endpoint. Live trading is architecturally blocked,
   not just disabled."
4. **30-second demo** — animated GIF or asciinema of a chat session
5. **Quickstart** — 4 commands: clone, set Alpaca keys + one LLM key,
   `docker compose -f docker-compose.minimal.yml up`, open browser
6. **Architecture diagram** — Mermaid, confirmation gate highlighted
7. **Feature list**
8. **How the confirmation gate works** — 2-turn flow diagram, token/TTL
9. **Add your own provider / agent / tool** — links to CONTRIBUTING + docs
10. **License** — Apache 2.0

### `docker-compose.minimal.yml`

3-container quickstart: `app`, `gateway`, `postgres`. No LiteLLM, Langfuse,
or Redis. Uses `ANTHROPIC_API_KEY` directly, in-memory cache, no tracing.
Fastest path to "clone and try it."

### CI

Single `.github/workflows/ci.yml`:

1. `lint` — ruff check + ruff format --check
2. `test` — pytest, matrix over Python 3.11 and 3.12
3. `docker-build` — smoke-test `docker compose -f docker-compose.minimal.yml
   up`, hit `/health`, assert `trading_mode == "paper"`
4. `evals-gate` — runs eval suite with cached LLM responses; blocks merge on
   regression

No deploy jobs.

### Docs (MkDocs Material)

`mkdocs.yml` nav rebuilt around the Alpaca-primary story. New pages of note:

- `docs/architecture/confirmation-gate.md`
- `docs/architecture/paper-trading-safety.md`
- `docs/providers/alpaca.md`
- `docs/agents/account-agent.md`
- `docs/agents/trade-agent.md`

Mermaid diagrams for LangGraph shape, two-turn confirmation sequence, and the
provider fallback chain.

## Decision log

| Decision | Choice | Alternatives considered |
|---|---|---|
| Positioning | Alpaca-first reference implementation | Generic fintech toolkit; multi-vendor neutral |
| Alpaca scope | Market data + paper trading **with** order placement (via confirmation gate) | Market data only; GET-only trading |
| MENA/Arabic features | Strip entirely, English + US only | Keep bilingual; keep everything |
| Repo history | Fresh repo, clean slate | Purge commit on existing repo; filter-repo rewrite |
| Name / license | `tradepilot` + Apache 2.0 | MIT; other names |
| Infra scope | Drop k8s, deploy workflows, site/; keep Langfuse + LiteLLM + gateway-as-service + evals framework | Keep everything; drop more |
| Paper-trading service shape | Protocol-based port + Alpaca adapter | Single concrete class named `alpaca_trading` |
| Confirmation UX | Two-turn with LangGraph interrupt + HMAC token + 60s TTL | Single-turn tool-call; JSON-schema-only validation |

## Next step

Invoke the `writing-plans` skill to produce a step-by-step implementation plan
derived from this design.
