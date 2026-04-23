# Safety

tradepilot is **paper trading only**. Five independent layers enforce that.

## 1. Config gate

The app refuses to boot unless `ALPACA_PAPER_ONLY=true`. A pydantic validator
raises on any other value.

## 2. Hardcoded URL allowlist

`AlpacaPaperTradingAdapter` constructs the Alpaca `TradingClient` with
`paper=True` and reads `_base_url` before every call. The paper URL is
hardcoded as `PAPER_BASE_URL`; the live URL is in `LIVE_BASE_URL_DENY`.
Any mismatch raises `RuntimeError`. No config can override either constant.

## 3. Startup verification

On gateway boot, `_verify_paper_trading()`:

1. Constructs the adapter.
2. Calls `get_account()`.
3. Asserts the resulting `Account.mode == "paper"`.

Failure at any step raises — uvicorn exits.

## 4. Schema-level flag on every trading block

`TradeIntentBlock`, `OrderResultBlock`, `AccountSummaryBlock`, and
`PositionsTableBlock` all carry `mode: Literal["paper"]`. Non-optional. Any
block with a missing or different `mode` value is dropped by the validator.

## 5. Validator rules

The validator node runs last. It drops trading blocks that don't carry
`mode="paper"`, strips text blocks that claim an order was placed when no
`order_result` block is present, and auto-injects a "paper trading only"
disclaimer when the response includes any trading block.

## Out-of-scope

- tradepilot does not contain an adapter that speaks to
  `api.alpaca.markets` (live).
- tradepilot does not persist, relay, or surface live credentials.
- tradepilot does not tell you what to buy. It does not make recommendations.
