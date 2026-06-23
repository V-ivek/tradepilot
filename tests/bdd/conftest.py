"""Shared pytest-bdd fixtures."""

import pytest

from tests.bdd.harness import Harness, build_harness, teardown_harness


@pytest.fixture
def harness(monkeypatch) -> Harness:
    h = build_harness(monkeypatch)
    try:
        yield h
    finally:
        teardown_harness(h)


@pytest.fixture
def ctx() -> dict:
    """Mutable per-scenario context for sharing state between steps."""
    return {}
