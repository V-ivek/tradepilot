import inspect

import pytest

from gateway.providers.base import DataProvider


def test_data_provider_is_abstract():
    with pytest.raises(TypeError):
        DataProvider()  # type: ignore[abstract]


def test_data_provider_has_required_async_methods():
    required = {
        "get_quote",
        "get_company_profile",
        "get_fundamentals",
        "get_price_history",
        "search_symbols",
        "get_news",
        "get_estimates",
        "get_analyst_data",
    }
    for name in required:
        method = getattr(DataProvider, name)
        assert inspect.iscoroutinefunction(method), f"{name} must be async"
