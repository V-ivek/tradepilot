"""Eval framework unit tests + dataset run against FakeAgentsTarget.

The dataset-level tests are marked ``eval`` so ``pytest -m eval`` runs them
as the CI evaluation gate, and the default ``pytest`` run skips them to
keep the fast suite focused.
"""

from pathlib import Path

import pytest

from evals.runner import EvalCase, run_dataset
from evals.scorers import SCORERS, contains, exact_match, regex
from evals.targets import FakeAgentsTarget

DATASETS_DIR = Path(__file__).parent / "datasets"


def test_exact_match():
    assert exact_match("x", "x") == (True, "")
    passed, _ = exact_match("x", "y")
    assert passed is False


def test_contains_substring():
    assert contains("Hello WORLD", "world")[0] is True
    passed, reason = contains("hello", "world")
    assert passed is False
    assert "world" in reason


def test_contains_with_list_expects_all():
    assert contains("paper trading only", ["paper", "only"])[0] is True
    passed, _ = contains("paper", ["paper", "live"])
    assert passed is False


def test_regex_scorer():
    assert regex("AAPL price 189.55", r"\d+\.\d+")[0] is True
    passed, _ = regex("no numbers", r"\d+")
    assert passed is False


async def test_runner_collates_results():
    async def target(s):
        return {"blocks": [{"type": "text", "content": s.upper()}]}

    cases = [
        EvalCase(id="a", input="hello", expected="HELLO"),
        EvalCase(id="b", input="hello", expected="WORLD"),
    ]
    report = await run_dataset("t", cases, target, SCORERS)

    assert report.pass_rate == 0.5


@pytest.mark.eval
@pytest.mark.parametrize(
    "dataset_name",
    [
        "guard",
        "stocks",
        "trading",
        "account",
        "fundamentals",
        "estimates",
        "finance",
        "news",
        "validator",
    ],
)
async def test_dataset_against_fake_target(dataset_name):
    dataset_path = DATASETS_DIR / f"{dataset_name}.yaml"
    if not dataset_path.exists():
        pytest.skip(f"{dataset_path} not yet written")

    from evals.runner import load_dataset

    cases = load_dataset(dataset_path)
    target = FakeAgentsTarget()
    report = await run_dataset(dataset_name, cases, target, SCORERS)

    # Minimum pass rate: 60% against the deterministic fake target. Real
    # targets will push this higher; adversarial cases are expected to pass
    # because the fake is hand-crafted to emit safe responses for them.
    assert report.pass_rate >= 0.6, f"{dataset_name}: {report.pass_rate:.0%} passed"
