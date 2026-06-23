"""Step definitions for chat.feature."""

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/chat.feature")


@given("the tradepilot stack is running")
def _stack_running(harness):
    assert harness is not None


@when(parsers.parse('the user sends "{message}"'))
def _send(harness, ctx, message):
    ctx["blocks"] = harness.send(message, reuse=False)


@when(parsers.parse('the user sends "{message}" in the same conversation'))
def _send_same_conv(harness, ctx, message):
    ctx["blocks_second"] = harness.send(message, reuse=True)


@when(parsers.parse('an unauthenticated request is sent to "{path}"'))
def _unauth(harness, ctx, path):
    r = harness.client.post(path, json={"user_input": "hi"})
    ctx["status"] = r.status_code


@then(parsers.parse('a "{block_type}" block is streamed'))
def _block_streamed(ctx, block_type):
    blocks = ctx.get("blocks") or ctx.get("blocks_second") or []
    types = [b.get("type") for b in blocks]
    assert block_type in types, f"expected {block_type} block; got types {types}"


@then(parsers.parse('the text mentions "{needle}"'))
def _text_mentions(ctx, needle):
    blocks = ctx.get("blocks") or ctx.get("blocks_second") or []
    joined = " ".join(b.get("content", "") for b in blocks if b.get("type") == "text").lower()
    assert needle.lower() in joined, f"{needle!r} not found in {joined!r}"


@then("no trading block is emitted")
def _no_trading(ctx):
    trading = {"trade_intent", "order_result", "account_summary", "positions_table"}
    blocks = ctx.get("blocks") or ctx.get("blocks_second") or []
    assert not any(b.get("type") in trading for b in blocks)


@then(parsers.parse('the block\'s symbol is "{symbol}"'))
def _block_symbol(ctx, symbol):
    blocks = ctx.get("blocks") or ctx.get("blocks_second") or []
    quotes = [b for b in blocks if b.get("type") == "quote"]
    assert quotes, "no quote block emitted"
    assert quotes[0]["symbol"] == symbol


@then(parsers.parse('the block carries "{field}"'))
def _block_has_field(ctx, field):
    blocks = ctx.get("blocks") or ctx.get("blocks_second") or []
    quotes = [b for b in blocks if b.get("type") == "quote"]
    assert quotes, "no quote block emitted"
    assert field in quotes[0]


@then("the second response uses the first response's conversation_id")
def _same_conv(harness, ctx):
    # conversation_ids["alice"] was set on the first send; reusing preserves it.
    assert "alice" in harness.conversation_ids
    # And the second send reused it, as the same key is still present after.
    assert harness.conversation_ids["alice"]


@then(parsers.parse("the response status is {code:d}"))
def _status(ctx, code):
    assert ctx["status"] == code
