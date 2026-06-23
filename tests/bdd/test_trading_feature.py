"""Step definitions for trading.feature."""

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/trading.feature")


@given("the tradepilot stack is running")
def _stack_running(harness):
    assert harness is not None


@when(parsers.parse('the user sends "{message}"'))
def _send(harness, ctx, message):
    ctx["blocks"] = harness.send(message, reuse=False)


@when(parsers.parse('the user sends "{message}" in the same conversation'))
def _send_same_conv(harness, ctx, message):
    ctx["blocks"] = harness.send(message, reuse=True)


# ---------- Given the user has a pending paper order for TSLA ----------


@given(parsers.parse("the user has a pending paper order for {symbol}"))
def _seed_pending(harness, ctx, symbol):
    # First turn: kicks off the two-turn flow so the conversation exists
    # and graph_state carries pending_trade.
    blocks = harness.send(f"Buy 10 {symbol} at market", reuse=False)
    ctx["first_blocks"] = blocks
    intent = next((b for b in blocks if b["type"] == "trade_intent"), None)
    assert intent is not None, f"expected trade_intent; got {[b['type'] for b in blocks]}"
    ctx["pending_symbol"] = symbol


@given("the pending draft has been tampered with")
def _tamper(harness, ctx):
    svc = harness.app.state.conversation_service
    conv_id = harness.conversation_ids["alice"]
    conv = svc.get_conversation(conv_id)
    assert conv is not None
    prior = conv.__dict__.get("graph_state", {})
    assert prior.get("pending_trade")
    prior["pending_trade"]["qty"] = "9999"  # mutate without re-signing
    conv.__dict__["graph_state"] = prior


# ---------- Then: block assertions ----------


def _blocks(ctx) -> list[dict]:
    return ctx.get("blocks") or []


@then(parsers.parse('a "{block_type}" block is streamed'))
@then(parsers.parse('an "{block_type}" block is streamed'))
def _block_streamed(ctx, block_type):
    blocks = _blocks(ctx)
    types = [b.get("type") for b in blocks]
    assert block_type in types, f"expected {block_type} block; got types {types}"


@then(parsers.parse('the block carries mode "{mode}"'))
def _block_mode(ctx, mode):
    blocks = _blocks(ctx)
    trading = [
        b
        for b in blocks
        if b.get("type") in {"trade_intent", "order_result", "account_summary", "positions_table"}
    ]
    assert trading, "no trading block to check"
    modes = [b.get("mode") for b in trading]
    assert all(m == mode for m in modes), f"bad modes: {modes}"


@then(parsers.parse('no "{block_type}" block is emitted in the same turn'))
@then(parsers.parse('no "{block_type}" block is emitted'))
def _no_block(ctx, block_type):
    blocks = _blocks(ctx)
    assert not any(b.get("type") == block_type for b in blocks), (
        f"unexpected {block_type} block in {blocks}"
    )


@then(parsers.parse("the conversation's graph state has awaiting_confirmation set to {value}"))
def _awaiting(harness, ctx, value):
    svc = harness.app.state.conversation_service
    conv_id = harness.conversation_ids["alice"]
    conv = svc.get_conversation(conv_id)
    assert conv is not None
    flag = conv.__dict__.get("graph_state", {}).get("awaiting_confirmation")
    expected = value.lower() == "true"
    assert bool(flag) is expected, f"awaiting_confirmation={flag!r}, expected {expected}"


@then(parsers.parse('the fake paper broker recorded a filled order for "{symbol}"'))
def _broker_recorded(harness, symbol):
    orders = [o for o in harness.broker._orders if o.symbol == symbol and o.status == "filled"]
    assert orders, f"no filled order for {symbol}; broker has {harness.broker._orders}"


@then("the fake paper broker has no recorded orders")
def _broker_empty(harness):
    assert harness.broker._orders == [], (
        f"broker recorded orders it shouldn't have: {harness.broker._orders}"
    )


@then(parsers.parse('a "text" block mentions "{needle}"'))
def _text_mentions(ctx, needle):
    blocks = _blocks(ctx)
    joined = " ".join(b.get("content", "") for b in blocks if b.get("type") == "text").lower()
    assert needle.lower() in joined, f"{needle!r} not found in {joined!r}"


@then(parsers.parse('at least one text block contains "{needle}"'))
def _text_contains(ctx, needle):
    blocks = _blocks(ctx)
    joined = " ".join(b.get("content", "") for b in blocks if b.get("type") == "text").lower()
    assert needle.lower() in joined, f"{needle!r} not found in {joined!r}"


@then(parsers.parse('an "{block_type}" block carries mode "{mode}"'))
def _named_block_mode(ctx, block_type, mode):
    blocks = _blocks(ctx)
    hits = [b for b in blocks if b.get("type") == block_type]
    assert hits, f"no {block_type} block emitted"
    assert all(b.get("mode") == mode for b in hits)
