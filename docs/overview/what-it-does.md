# What it does

tradepilot is a conversational assistant for US equity markets. It can:

- Answer **finance and investing** questions ("what's a limit order?").
- Look up **stock quotes, charts, and news** by ticker or company name.
- Pull **fundamentals** (ratios, statements, filings) and **estimates**
  (EPS/revenue consensus, analyst price targets).
- Report your **paper-trading account**: balances, open positions, order
  history, portfolio equity curve.
- **Place paper orders** behind a two-turn human-in-the-loop confirmation.

Everything trading-related is paper-only. Live trading is not a toggle — the
adapter that would speak to the live endpoint does not exist in this repo.
