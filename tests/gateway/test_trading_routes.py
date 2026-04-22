from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from gateway.deps import get_paper_trading
from gateway.main import create_app
from tests.gateway.fakes.paper_trading import FakePaperTradingAdapter


@pytest.fixture(autouse=True)
def _no_alpaca_keys(monkeypatch):
    """Ensure the lifespan startup check hits the dev-mode (no-keys) branch."""
    monkeypatch.setenv("ALPACA_API_KEY_ID", "")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "")


@pytest.fixture
def fake():
    return FakePaperTradingAdapter(starting_cash=Decimal("1000"), fill_price=Decimal("100"))


@pytest.fixture
def client(fake):
    app = create_app()
    app.dependency_overrides[get_paper_trading] = lambda: fake
    with TestClient(app) as c:
        yield c


def test_get_account_returns_paper_account(client):
    r = client.get("/account")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "paper"
    assert body["cash"] == "1000"


def test_account_503_when_adapter_missing():
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/account")
    assert r.status_code == 503


def test_place_and_list_orders(client):
    r = client.post(
        "/orders",
        json={"symbol": "AAPL", "side": "buy", "qty": "2", "type": "market"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "filled"
    assert body["mode"] == "paper"

    r2 = client.get("/orders")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_list_positions_after_buy(client):
    client.post(
        "/orders",
        json={"symbol": "AAPL", "side": "buy", "qty": "2", "type": "market"},
    )
    r = client.get("/positions")
    assert r.status_code == 200
    positions = r.json()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"


def test_cancel_order(client):
    order = client.post(
        "/orders",
        json={"symbol": "AAPL", "side": "buy", "qty": "1", "type": "market"},
    ).json()

    r = client.delete(f"/orders/{order['order_id']}")
    assert r.status_code == 204

    orders = client.get("/orders", params={"status": "canceled"}).json()
    assert len(orders) == 1


def test_portfolio_history(client):
    r = client.get("/portfolio/history", params={"period": "1M"})
    assert r.status_code == 200
    body = r.json()
    assert "timestamps" in body
    assert body["base_value"] == "100000"


def test_list_orders_filter_by_status(client):
    client.post(
        "/orders",
        json={"symbol": "AAPL", "side": "buy", "qty": "1", "type": "market"},
    )
    r = client.get("/orders", params={"status": "filled"})
    assert r.status_code == 200
    assert len(r.json()) == 1
