"""Demo-mode dev server for testing the debug chat without API keys.

Boots the real tradepilot app (real graph wiring, real confirmation gate,
real HMAC order drafts) with:

- deterministic fake LLM nodes (no Anthropic/OpenAI key needed)
- an in-memory FakePaperTradingAdapter (no Alpaca key needed)
- the real gateway app served in-process via httpx.ASGITransport

Usage:
    uv run python tools/dev_server.py            # serves on :4700

Switch to the real stack later by filling .env and running
`docker compose -f docker-compose.minimal.yml up`.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Settings env must exist before any src import resolves get_settings().
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LITELLM_BASE_URL", "http://localhost:9")
os.environ.setdefault("ALPACA_PAPER_ONLY", "true")
os.environ.setdefault("ALPACA_API_KEY_ID", "")
os.environ.setdefault("ALPACA_API_SECRET_KEY", "")
os.environ.setdefault("JWT_SECRET", "dev-secret-change-me")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "120")

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from gateway import main as gateway_main  # noqa: E402
from gateway.deps import get_paper_trading, get_registry  # noqa: E402
from gateway.providers.registry import ProviderRegistry  # noqa: E402
from src.agent.graph import build_graph  # noqa: E402
from src.api.routes import chat as chat_route  # noqa: E402
from src.main import create_app  # noqa: E402
from src.services.gateway import GatewayClient, set_gateway_client  # noqa: E402
from tests.bdd import harness as demo  # noqa: E402
from tests.gateway.fakes.paper_trading import FakePaperTradingAdapter  # noqa: E402

# The fake trade agent signs drafts with harness JWT_SECRET; align the app's.
os.environ["JWT_SECRET"] = demo.JWT_SECRET

from src.config.settings import get_settings  # noqa: E402

get_settings.cache_clear()


def build_demo_app():
    # Real gateway app, fake broker + fake market data.
    gateway_app = gateway_main.create_app()
    broker = FakePaperTradingAdapter(starting_cash=Decimal("100000"), fill_price=Decimal("189.55"))
    registry = ProviderRegistry([demo._FakeDataProvider()])
    gateway_app.state.paper_trading = broker
    gateway_app.dependency_overrides[get_registry] = lambda: registry
    gateway_app.dependency_overrides[get_paper_trading] = lambda: broker

    # In-process HTTP from the app's GatewayClient to the gateway ASGI app.
    transport = httpx.ASGITransport(app=gateway_app)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://gateway")
    set_gateway_client(GatewayClient(base_url="http://gateway", client=http_client))

    # Real app; graph uses the harness's deterministic fake nodes.
    # get_graph is called directly by the route (not via Depends), so rebind
    # the module attribute rather than using dependency_overrides.
    app = create_app()
    demo_graph = build_graph(nodes=demo.FAKE_NODES)
    chat_route.get_graph = lambda request: demo_graph
    return app


app = build_demo_app()


if __name__ == "__main__":
    print()
    print("=" * 64)
    print("tradepilot DEMO server — paper trading, deterministic agents")
    print("No LLM or Alpaca keys required. Things you can try in the chat:")
    print("  - \"What's AAPL's price?\"")
    print('  - "Show my account"')
    print('  - "Buy 5 TSLA at market"  → then reply "confirm" or "cancel"')
    print('  - "What\'s the weather?"  → off-topic rejection')
    print("=" * 64)
    print()
    uvicorn.run(app, host="127.0.0.1", port=4700, log_level="info")
