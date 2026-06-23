"""Step definitions for paper_safety.feature."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from pytest_bdd import given, parsers, scenarios, then, when

from src.agent.nodes.validator import validator_node
from src.models.order import OrderDraft, new_nonce, sign_order, verify_order_token

scenarios("features/paper_safety.feature")

SECRET = "safety-secret"


# ---------- Live-endpoint refusal ----------


@when("an AlpacaPaperTradingAdapter is constructed against the live base URL")
def _construct_live(ctx):
    from gateway.services.paper_trading_alpaca import (
        LIVE_BASE_URL_DENY,
        AlpacaPaperTradingAdapter,
    )

    client = MagicMock()
    client._base_url = LIVE_BASE_URL_DENY
    try:
        AlpacaPaperTradingAdapter(key_id="k", secret="s", client=client)
        ctx["raised"] = None
    except RuntimeError as e:
        ctx["raised"] = e


@then(parsers.parse('a RuntimeError is raised mentioning "{needle}"'))
def _raised_runtime(ctx, needle):
    assert isinstance(ctx["raised"], RuntimeError), f"got {ctx['raised']!r}"
    assert needle.lower() in str(ctx["raised"]).lower(), ctx["raised"]


# ---------- Expired token ----------


def _draft_data(minutes_old: int = 0, **overrides) -> dict:
    from datetime import timedelta

    created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_old)
    data = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": Decimal("1"),
        "type": "market",
        "limit_price": None,
        "stop_price": None,
        "time_in_force": "day",
        "estimated_cost": Decimal("100"),
        "nonce": new_nonce(),
        "created_at": created_at,
        "mode": "paper",
    }
    data.update(overrides)
    data["confirmation_token"] = sign_order(data, SECRET)
    return data


@given(parsers.parse("a signed order draft created {minutes:d} minutes ago"))
def _old_draft(ctx, minutes):
    ctx["draft"] = OrderDraft.model_validate(_draft_data(minutes_old=minutes))


@given("a freshly signed order draft")
def _fresh_draft(ctx):
    ctx["draft_data"] = _draft_data(minutes_old=0)
    ctx["draft"] = OrderDraft.model_validate(ctx["draft_data"])


@given("the draft's quantity has been silently mutated")
def _mutate(ctx):
    mutated = ctx["draft"].model_copy(update={"qty": Decimal("1000")})
    ctx["draft"] = mutated


@then("verify_order_token returns False")
def _verify_false(ctx):
    assert verify_order_token(ctx["draft"], SECRET) is False


# ---------- Validator drops non-paper trading blocks ----------


@given(parsers.parse('a trade_intent block with mode "{mode}"'))
def _intent_block(ctx, mode):
    ctx["block"] = {
        "type": "trade_intent",
        "symbol": "AAPL",
        "side": "buy",
        "qty": "1",
        "order_type": "market",
        "estimated_cost": "100",
        "confirmation_token": "tok",
        "mode": mode,
    }


@when("the validator runs")
def _run_validator(ctx):
    state = {"blocks": [ctx["block"]]}
    ctx["out"] = asyncio.run(validator_node(state))


@then("the trade_intent block is dropped")
def _dropped(ctx):
    blocks = ctx["out"]["blocks"]
    assert all(b.get("type") != "trade_intent" for b in blocks), blocks
