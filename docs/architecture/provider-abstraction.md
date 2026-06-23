# Provider abstraction

The gateway fronts all external data and trading calls. Two parallel
ports-and-adapters:

## Market data

```
gateway/providers/
├── base.py          # DataProvider ABC
├── registry.py      # ProviderRegistry with fallback chain
├── factory.py       # wires Alpaca → Finnhub → Alpha Vantage
├── alpaca.py
├── finnhub.py
└── alpha_vantage.py
```

The registry tries each provider in order; on `None`, empty list, or
exception it falls through to the next. Alpaca is primary for quotes,
bars, news, symbol search, and company profiles. Finnhub covers
fundamentals, estimates, and analyst data. Alpha Vantage adds a stronger
symbol-search path.

Adding a new provider is three files: an `impl`, a test, and registering
it in `factory.py`.

## Paper trading

```
gateway/services/
├── paper_trading.py         # PaperTradingService Protocol + DTOs
└── paper_trading_alpaca.py  # AlpacaPaperTradingAdapter
```

Routes and tests depend on the Protocol, never on the concrete class. The
seam is preserved for a future second adapter (another broker's paper API)
without touching call sites.

## Gateway routes

Every agent-side tool calls the gateway over HTTP. The gateway is the only
thing in the system that imports the Alpaca SDK. The agent graph is
provider-agnostic.
