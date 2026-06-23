from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway.config import get_settings
from gateway.main import create_app


def test_startup_skipped_when_alpaca_keys_unset(monkeypatch, caplog):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "")
    get_settings.cache_clear()

    app = create_app()
    with caplog.at_level("WARNING"), TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
    assert any("skipping paper-trading verification" in rec.message for rec in caplog.records)


def test_startup_raises_when_adapter_construction_fails(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "bad")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "bad")
    get_settings.cache_clear()

    with patch(
        "gateway.main.AlpacaPaperTradingAdapter",
        side_effect=RuntimeError("boom"),
    ):
        app = create_app()
        with pytest.raises(RuntimeError, match="boom"):
            with TestClient(app):
                pass


def test_startup_raises_when_account_mode_is_not_paper(monkeypatch):
    from decimal import Decimal

    from gateway.services.paper_trading import Account

    monkeypatch.setenv("ALPACA_API_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "s")
    get_settings.cache_clear()

    class _AdapterWithFakeAccount:
        def __init__(self, **kwargs):
            pass

        async def get_account(self):
            # Bypass the Literal["paper"] restriction by patching the Account class
            acct = Account(
                equity=Decimal("1"),
                cash=Decimal("1"),
                buying_power=Decimal("1"),
                day_trade_count=0,
                positions_count=0,
            )
            object.__setattr__(acct, "__dict__", {**acct.__dict__, "mode": "live"})
            return acct

    with patch("gateway.main.AlpacaPaperTradingAdapter", _AdapterWithFakeAccount):
        app = create_app()
        with pytest.raises(RuntimeError, match="expected 'paper'"):
            with TestClient(app):
                pass


def test_startup_succeeds_with_valid_paper_adapter(monkeypatch):
    from decimal import Decimal

    from gateway.services.paper_trading import Account

    monkeypatch.setenv("ALPACA_API_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "s")
    get_settings.cache_clear()

    class _GoodAdapter:
        def __init__(self, **kwargs):
            pass

        async def get_account(self):
            return Account(
                equity=Decimal("100000"),
                cash=Decimal("100000"),
                buying_power=Decimal("100000"),
                day_trade_count=0,
                positions_count=0,
            )

    with patch("gateway.main.AlpacaPaperTradingAdapter", _GoodAdapter):
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/health")
        assert r.status_code == 200
        assert app.state.paper_trading is not None
