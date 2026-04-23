# Changelog

All notable changes to this project will be documented in this file. The
format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Initial public release scaffold (Phases 0–11).

## [0.1.0] — TBD

### Added
- `app` FastAPI service hosting a LangGraph agent graph:
  topic guard, router, seven specialist agents (news, stock, finance,
  fundamentals, estimates, account, trade), a two-turn confirmation gate,
  and a rule-based validator.
- `gateway` FastAPI service:
  - `DataProvider` ABC with a fallback chain (Alpaca → Finnhub → Alpha Vantage).
  - `PaperTradingService` Protocol with a single `AlpacaPaperTradingAdapter`.
  - Paper-mode startup verification — gateway exits on any paper-mode
    assertion failure.
- SSE chat endpoint, conversation list/get/delete, JWT auth, per-user
  rate limiting.
- HMAC-signed `OrderDraft` with 60-second TTL; graph-level tests that assert
  the confirmation gate property.
- Response blocks as a Pydantic discriminated union; validator drops any
  trading block that doesn't carry `mode="paper"`.
- Streamlit chat UI with amber PAPER banner and confirm/cancel buttons on
  trade-intent blocks.
- Evals framework with YAML datasets for nine categories.
- Docker images for app, gateway, and chat-ui; full and minimal compose
  files; GitHub Actions CI covering lint, tests, docker build health, and
  the evals gate.
- MkDocs site.

### Safety
- `ALPACA_PAPER_ONLY` required at startup.
- Hardcoded live-URL denylist enforced by `_assert_paper()` before every
  trading I/O.
- Schema-level `mode: Literal["paper"]` on every trading block.
