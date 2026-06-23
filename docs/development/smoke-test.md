# v0.1.0 smoke test

Run against the minimal stack before tagging `v0.1.0`.

## Setup

```bash
docker compose -f docker-compose.minimal.yml up --build -d
```

## Checks

1. **App health** — `curl localhost:4700/health`
   - ✅ `status == "ok"`
   - ✅ `trading_mode == "paper"`

2. **Gateway health** — `curl localhost:4706/health`
   - ✅ `status == "ok"`
   - ✅ `trading_mode == "paper"`
   - ✅ `providers` includes `AlpacaProvider`

3. **Stock quote** — chat "What's AAPL's price?"
   - ✅ `quote` block streamed with a non-zero price

4. **Account** — chat "What's in my paper account?"
   - ✅ `account_summary` block with `mode: "paper"`
   - ✅ `positions_table` block (possibly empty)
   - ✅ response text mentions "paper trading"

5. **Buy intent** — chat "Buy 1 share of AAPL at market"
   - ✅ `trade_intent` block with a `confirmation_token`
   - ✅ block carries `mode: "paper"`
   - ✅ visible PAPER pill in the UI
   - ✅ graph turn ends; no order placed

6. **Confirm** — reply "confirm"
   - ✅ `order_result` block with `filled` status
   - ✅ `mode: "paper"`
   - ✅ state cleared — following message does not resurrect the pending trade

7. **Orders list** — chat "Show my orders"
   - ✅ The order from step 6 appears

## Verification checklist

- [ ] Every trading block carries `mode: "paper"`.
- [ ] Every trading response contains the phrase "paper trading" in text.
- [ ] Structured logs (`docker compose logs app`) include
      `"mode": "paper"` on trading events.
- [ ] Langfuse (full stack at `:4702`) shows traces with `mode=paper`
      metadata.
- [ ] Attempting to edit `gateway/services/paper_trading_alpaca.py` to point
      at the live URL makes the gateway refuse to start.
- [ ] `pytest -m eval` passes against `FakeAgentsTarget`.

## Tag

Once all checks pass:

```bash
git tag -s v0.1.0 -m "tradepilot v0.1.0"
git push origin v0.1.0
```
