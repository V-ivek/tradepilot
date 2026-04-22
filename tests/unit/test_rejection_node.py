from src.agent.nodes.rejection import rejection_node


async def test_rejection_emits_text_block():
    state = {}
    out = await rejection_node(state)

    assert len(out["blocks"]) == 1
    block = out["blocks"][0]
    assert block["type"] == "text"
    assert "help" in block["content"].lower() or "outside" in block["content"].lower()


async def test_rejection_appends_to_existing_blocks():
    state = {"blocks": [{"type": "text", "content": "prior"}]}
    out = await rejection_node(state)

    assert len(out["blocks"]) == 2
    assert out["blocks"][0]["content"] == "prior"
