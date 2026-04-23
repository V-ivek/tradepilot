from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.models.order import (
    TOKEN_TTL_SECONDS,
    OrderDraft,
    new_nonce,
    sign_order,
    verify_order_token,
)

SECRET = "test-secret"


def _valid_draft_data(type_="market", **overrides):
    data = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": Decimal("10"),
        "type": type_,
        "time_in_force": "day",
        "estimated_cost": Decimal("1000"),
        "nonce": new_nonce(),
        "created_at": datetime.now(timezone.utc),
        "mode": "paper",
    }
    data.update(overrides)
    return data


def _signed(type_="market", **overrides):
    data = _valid_draft_data(type_=type_, **overrides)
    data["confirmation_token"] = sign_order(data, SECRET)
    return OrderDraft(**data)


def test_valid_market_draft_roundtrips():
    draft = _signed()
    assert OrderDraft.model_validate(draft.model_dump()) == draft


def test_limit_order_requires_limit_price():
    with pytest.raises(ValueError, match="limit_price"):
        _signed(type_="limit")  # no limit_price


def test_limit_order_with_limit_price_is_valid():
    draft = _signed(type_="limit", limit_price=Decimal("180"))
    assert draft.limit_price == Decimal("180")


def test_stop_order_requires_stop_price():
    with pytest.raises(ValueError, match="stop_price"):
        _signed(type_="stop")


def test_stop_limit_requires_both_prices():
    with pytest.raises(ValueError):
        _signed(type_="stop_limit", stop_price=Decimal("170"))  # limit_price missing


def test_qty_must_be_positive():
    with pytest.raises(ValueError):
        _signed(qty=Decimal("0"))


def test_verify_valid_token():
    draft = _signed()
    assert verify_order_token(draft, SECRET) is True


def test_verify_rejects_tampered_token():
    draft = _signed()
    tampered = draft.model_copy(update={"qty": Decimal("1000")})
    assert verify_order_token(tampered, SECRET) is False


def test_verify_rejects_tampered_symbol():
    draft = _signed()
    tampered = draft.model_copy(update={"symbol": "TSLA"})
    assert verify_order_token(tampered, SECRET) is False


def test_verify_rejects_wrong_secret():
    draft = _signed()
    assert verify_order_token(draft, "different-secret") is False


def test_verify_rejects_expired_draft():
    data = _valid_draft_data()
    data["created_at"] = datetime.now(timezone.utc) - timedelta(seconds=TOKEN_TTL_SECONDS + 5)
    data["confirmation_token"] = sign_order(data, SECRET)
    draft = OrderDraft(**data)

    assert verify_order_token(draft, SECRET) is False


def test_new_nonce_is_unique_and_hex():
    a, b = new_nonce(), new_nonce()
    assert a != b
    assert len(a) == 32
    int(a, 16)  # parseable as hex


def test_verify_uses_constant_time_compare(monkeypatch):
    calls = {"n": 0}

    def counting(a, b):
        calls["n"] += 1
        return a == b

    monkeypatch.setattr("src.models.order.hmac.compare_digest", counting)
    draft = _signed()
    verify_order_token(draft, SECRET)
    assert calls["n"] == 1


def test_modified_nonce_breaks_verification():
    draft = _signed()
    tampered = draft.model_copy(update={"nonce": new_nonce()})
    assert verify_order_token(tampered, SECRET) is False
