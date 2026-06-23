from decimal import Decimal

import httpx
import pytest
import respx

from src.services.gateway import GatewayClient


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        async with GatewayClient(base_url="http://gw:8000", client=http) as c:
            yield c


@respx.mock
async def test_get_quote_happy_path(client):
    respx.get("http://gw:8000/quote/AAPL").respond(json={"ticker": "AAPL", "price": "189.55"})

    q = await client.get_quote("aapl")

    assert q is not None
    assert q.ticker == "AAPL"
    assert q.price == Decimal("189.55")


@respx.mock
async def test_get_quote_returns_none_on_404(client):
    respx.get("http://gw:8000/quote/ZZZ").respond(status_code=404)
    assert await client.get_quote("ZZZ") is None


@respx.mock
async def test_retries_once_on_5xx(client):
    route = respx.get("http://gw:8000/quote/AAPL")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"ticker": "AAPL", "price": "1"}),
    ]

    q = await client.get_quote("AAPL")

    assert q is not None
    assert route.call_count == 2


@respx.mock
async def test_gives_up_after_two_attempts(client):
    route = respx.get("http://gw:8000/quote/AAPL")
    route.side_effect = [httpx.Response(503), httpx.Response(502)]

    q = await client.get_quote("AAPL")

    assert q is None
    assert route.call_count == 2


@respx.mock
async def test_timeout_retried_once(client):
    route = respx.get("http://gw:8000/quote/AAPL")
    route.side_effect = [
        httpx.TimeoutException("slow"),
        httpx.Response(200, json={"ticker": "AAPL", "price": "1"}),
    ]

    q = await client.get_quote("AAPL")
    assert q is not None


@respx.mock
async def test_search_symbols(client):
    respx.get("http://gw:8000/search").respond(json=[{"ticker": "AAPL", "name": "Apple Inc"}])

    matches = await client.search_symbols("apple")
    assert len(matches) == 1


@respx.mock
async def test_list_positions_returns_empty_on_error(client):
    respx.get("http://gw:8000/positions").respond(status_code=503)
    positions = await client.list_positions()
    # One retry => still 503 => empty
    assert positions == []


@respx.mock
async def test_place_order_serializes_request(client):
    from gateway.services.paper_trading import OrderRequest

    route = respx.post("http://gw:8000/orders").respond(
        json={
            "order_id": "x",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "1",
            "type": "market",
            "status": "filled",
            "filled_qty": "1",
            "filled_avg_price": "100",
            "submitted_at": "2026-04-22T10:00:00+00:00",
            "mode": "paper",
        }
    )

    req = OrderRequest(symbol="AAPL", side="buy", qty=Decimal("1"), type="market")
    result = await client.place_order(req)

    assert result is not None
    assert result.order_id == "x"
    assert result.mode == "paper"
    assert route.called


@respx.mock
async def test_cancel_order_returns_true_on_204(client):
    respx.delete("http://gw:8000/orders/xyz").respond(status_code=204)
    assert await client.cancel_order("xyz") is True


@respx.mock
async def test_health_returns_json(client):
    respx.get("http://gw:8000/health").respond(
        json={"status": "ok", "trading_mode": "paper", "providers": []}
    )
    health = await client.health()
    assert health["trading_mode"] == "paper"
