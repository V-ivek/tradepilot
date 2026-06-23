from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from src.agent.nodes.confirmation_classifier import confirmation_classifier_node


def _llm(content: str):
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


@pytest.mark.parametrize(
    "user_input,verdict_json",
    [
        ("confirm", '{"verdict": "AFFIRM"}'),
        ("yes", '{"verdict": "AFFIRM"}'),
        ("do it", '{"verdict": "AFFIRM"}'),
        ("place it", '{"verdict": "AFFIRM"}'),
        ("go ahead", '{"verdict": "AFFIRM"}'),
        ("submit the order", '{"verdict": "AFFIRM"}'),
        ("proceed", '{"verdict": "AFFIRM"}'),
    ],
)
async def test_affirm_phrases(user_input, verdict_json):
    llm = _llm(verdict_json)
    state = {"user_input": user_input}

    out = await confirmation_classifier_node(state, model=llm)

    assert out["confirmation_verdict"] == "AFFIRM"


@pytest.mark.parametrize(
    "verdict_json",
    [
        '{"verdict": "DENY"}',
        '{"verdict": "DENY"}',
        '{"verdict": "DENY"}',
    ],
)
@pytest.mark.parametrize("user_input", ["cancel", "no", "nevermind", "stop", "abort"])
async def test_deny_phrases(user_input, verdict_json):
    llm = _llm(verdict_json)
    state = {"user_input": user_input}

    out = await confirmation_classifier_node(state, model=llm)
    assert out["confirmation_verdict"] == "DENY"


async def test_modify_with_edits():
    llm = _llm('{"verdict": "MODIFY", "edits": {"qty": "5"}}')
    state = {"user_input": "change qty to 5"}

    out = await confirmation_classifier_node(state, model=llm)

    assert out["confirmation_verdict"] == "MODIFY"
    assert out["pending_edits"] == {"qty": "5"}


async def test_modify_with_limit_price():
    llm = _llm('{"verdict": "MODIFY", "edits": {"type": "limit", "limit_price": "180"}}')
    state = {"user_input": "make it a limit at 180"}

    out = await confirmation_classifier_node(state, model=llm)

    assert out["confirmation_verdict"] == "MODIFY"
    assert out["pending_edits"]["type"] == "limit"


@pytest.mark.parametrize(
    "user_input,verdict_json",
    [
        ("what's AAPL?", '{"verdict": "UNRELATED"}'),
        ("hmm", '{"verdict": "UNRELATED"}'),
        ("?", '{"verdict": "UNRELATED"}'),
    ],
)
async def test_unrelated_phrases(user_input, verdict_json):
    llm = _llm(verdict_json)
    state = {"user_input": user_input}

    out = await confirmation_classifier_node(state, model=llm)
    assert out["confirmation_verdict"] == "UNRELATED"


async def test_unparseable_response_defaults_unrelated():
    llm = _llm("I think so?")
    state = {"user_input": "x"}

    out = await confirmation_classifier_node(state, model=llm)
    assert out["confirmation_verdict"] == "UNRELATED"


async def test_invalid_verdict_defaults_unrelated():
    llm = _llm('{"verdict": "MAYBE"}')
    state = {"user_input": "x"}

    out = await confirmation_classifier_node(state, model=llm)
    assert out["confirmation_verdict"] == "UNRELATED"


async def test_handles_code_fence():
    llm = _llm('```json\n{"verdict": "AFFIRM"}\n```')
    state = {"user_input": "yes"}

    out = await confirmation_classifier_node(state, model=llm)
    assert out["confirmation_verdict"] == "AFFIRM"


async def test_modify_without_edits_has_no_pending_edits():
    llm = _llm('{"verdict": "MODIFY"}')
    state = {"user_input": "change something"}

    out = await confirmation_classifier_node(state, model=llm)
    assert out["confirmation_verdict"] == "MODIFY"
    assert "pending_edits" not in out
