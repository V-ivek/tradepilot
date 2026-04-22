import pytest

from src.agent.nodes.validator import validator_node


async def _run(blocks):
    state = {"blocks": list(blocks)}
    return await validator_node(state)


# --- PII scrubbing --------------------------------------------------------


@pytest.mark.parametrize(
    "input_text,not_in",
    [
        ("Email me at alice@example.com", "alice@example.com"),
        ("Call 555-123-4567 today", "555-123-4567"),
        ("Call (555) 123-4567 today", "(555) 123-4567"),
        ("SSN 123-45-6789", "123-45-6789"),
    ],
)
async def test_pii_is_redacted(input_text, not_in):
    out = await _run([{"type": "text", "content": input_text}])
    content = out["blocks"][0]["content"]
    assert not_in not in content
    assert "[redacted]" in content


# --- disclaimer injection -------------------------------------------------


async def test_disclaimer_injected_for_quote_block():
    out = await _run(
        [{"type": "quote", "symbol": "AAPL", "price": "100", "change": "0", "change_pct": "0"}]
    )
    text_blocks = [b for b in out["blocks"] if b["type"] == "text"]
    assert any("educational" in b["content"].lower() for b in text_blocks)


async def test_no_disclaimer_for_text_only_response():
    out = await _run([{"type": "text", "content": "Here's how PE works."}])
    text_blocks = [b for b in out["blocks"] if b["type"] == "text"]
    assert len(text_blocks) == 1
    assert "educational" not in text_blocks[0]["content"].lower()


async def test_no_duplicate_disclaimer():
    out = await _run(
        [
            {
                "type": "chart",
                "symbol": "AAPL",
                "timeframe": "1M",
                "data": [{"t": 1}],
            },
            {
                "type": "text",
                "content": "This is educational information, nothing personalized.",
            },
        ]
    )
    texts = [b for b in out["blocks"] if b["type"] == "text"]
    # Validator should not add another disclaimer since one already looks like one.
    educational_count = sum(1 for t in texts if "educational" in t["content"].lower())
    assert educational_count == 1


# --- empty-required-field rejection ---------------------------------------


async def test_drops_quote_block_missing_price():
    out = await _run([{"type": "quote", "symbol": "AAPL"}])
    assert all(b["type"] != "quote" for b in out["blocks"])


async def test_drops_trade_intent_missing_estimated_cost():
    out = await _run(
        [
            {
                "type": "trade_intent",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "1",
                "order_type": "market",
                "confirmation_token": "tok",
                # estimated_cost missing
            }
        ]
    )
    assert all(b["type"] != "trade_intent" for b in out["blocks"])


async def test_keeps_valid_blocks():
    out = await _run(
        [
            {
                "type": "quote",
                "symbol": "AAPL",
                "price": "100",
                "change": "0",
                "change_pct": "0",
            },
            {"type": "text", "content": "clean"},
        ]
    )
    assert sum(1 for b in out["blocks"] if b["type"] == "quote") == 1


async def test_unknown_block_types_passthrough():
    out = await _run([{"type": "custom", "foo": "bar"}])
    assert any(b.get("type") == "custom" for b in out["blocks"])
