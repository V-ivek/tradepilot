from src.agent.nodes.confirmation import confirmation_gate_node


async def test_gate_is_noop_when_awaiting():
    state = {
        "pending_trade": {"symbol": "AAPL"},
        "awaiting_confirmation": True,
        "blocks": [{"type": "trade_intent"}],
    }

    out = await confirmation_gate_node(state)

    assert out["pending_trade"] == {"symbol": "AAPL"}
    assert out["awaiting_confirmation"] is True
    assert out["blocks"] == [{"type": "trade_intent"}]


async def test_gate_passes_state_through_when_idle():
    state = {"blocks": []}
    out = await confirmation_gate_node(state)
    assert out == state
