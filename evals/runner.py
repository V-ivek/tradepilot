"""Minimal eval runner.

Loads YAML dataset files into ``EvalCase`` objects and runs each case
against a ``Target``. A ``Scorer`` decides pass/fail. Results are collated
into an ``EvalReport``.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml


@dataclass
class EvalCase:
    id: str
    input: str
    expected: Any
    scorer: str = "contains"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    actual: Any
    reason: str = ""


@dataclass
class EvalReport:
    dataset: str
    results: list[EvalResult]

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)


def load_dataset(path: Path) -> list[EvalCase]:
    raw = yaml.safe_load(path.read_text())
    out: list[EvalCase] = []
    for entry in raw or []:
        out.append(
            EvalCase(
                id=entry["id"],
                input=entry["input"],
                expected=entry.get("expected"),
                scorer=entry.get("scorer", "contains"),
                metadata=entry.get("metadata", {}),
            )
        )
    return out


async def run_dataset(
    dataset: str,
    cases: list[EvalCase],
    target: Callable[[str], Any],
    scorers: dict[str, Callable[[Any, Any], tuple[bool, str]]],
) -> EvalReport:
    results: list[EvalResult] = []
    for case in cases:
        actual = await target(case.input)
        scorer = scorers.get(case.scorer)
        if scorer is None:
            results.append(EvalResult(case.id, False, actual, f"unknown scorer {case.scorer}"))
            continue
        passed, reason = scorer(actual, case.expected)
        results.append(EvalResult(case.id, passed, actual, reason))
    return EvalReport(dataset=dataset, results=results)
