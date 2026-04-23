# Quickstart

The minimal stack runs three containers: `app`, `gateway`, `postgres`.

## 1. Clone

```bash
git clone https://github.com/anthropics/tradepilot.git
cd tradepilot
```

## 2. Provide keys

Create `.env` from the template:

```bash
cp .env.example .env
```

Then fill in two values:

- `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY` — free paper-trading keys
  from [alpaca.markets](https://app.alpaca.markets).
- `ANTHROPIC_API_KEY` — your Anthropic API key.

Leave `ALPACA_PAPER_ONLY=true`. The app refuses to boot otherwise.

## 3. Launch

```bash
docker compose -f docker-compose.minimal.yml up --build
```

Health check:

```bash
curl localhost:4700/health
# {"status":"ok","trading_mode":"paper"}
```

## 4. Chat

Open `http://localhost:4700/docs` and use the interactive Swagger page, or
spin up the full stack (`docker compose up`) to get the Streamlit chat UI on
`http://localhost:4705`.
