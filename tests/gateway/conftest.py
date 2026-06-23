"""Shared gateway-test fixtures.

Multiple test files mutate ``ALPACA_*`` env vars for their own scenarios.
``get_settings`` is ``@lru_cache``'d, so without explicit cache busting a
Settings object cached by one test can leak into the next. This autouse
fixture clears the cache before and after every gateway test to keep them
isolated.
"""

import pytest

from gateway.config import get_settings


@pytest.fixture(autouse=True)
def _reset_gateway_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
