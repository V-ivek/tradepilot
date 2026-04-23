"""Scorers for eval cases."""

import re
from typing import Any


def exact_match(actual: Any, expected: Any) -> tuple[bool, str]:
    if actual == expected:
        return True, ""
    return False, f"expected {expected!r}, got {actual!r}"


def contains(actual: Any, expected: Any) -> tuple[bool, str]:
    actual_str = _flatten(actual)
    if isinstance(expected, list):
        missing = [e for e in expected if str(e).lower() not in actual_str.lower()]
        return (not missing, f"missing: {missing}" if missing else "")
    needle = str(expected).lower()
    if needle in actual_str.lower():
        return True, ""
    return False, f"expected substring {needle!r} not in {actual_str!r}"


def regex(actual: Any, expected: Any) -> tuple[bool, str]:
    actual_str = _flatten(actual)
    pattern = re.compile(str(expected), re.IGNORECASE | re.DOTALL)
    if pattern.search(actual_str):
        return True, ""
    return False, f"pattern {expected!r} did not match {actual_str!r}"


def llm_judge(actual: Any, expected: Any) -> tuple[bool, str]:
    # Deterministic stub: production swaps in a real LLM judge.
    return contains(actual, expected)


SCORERS = {
    "exact_match": exact_match,
    "contains": contains,
    "regex": regex,
    "llm_judge": llm_judge,
}


def _flatten(actual: Any) -> str:
    if isinstance(actual, str):
        return actual
    if isinstance(actual, dict):
        return " ".join(f"{k}={_flatten(v)}" for k, v in actual.items())
    if isinstance(actual, list):
        return " ".join(_flatten(x) for x in actual)
    return str(actual)
