import pytest
from pydantic import ValidationError

from src.config.settings import Settings, get_settings  # noqa: F401


def _set_required_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")


def test_settings_require_paper_only_true(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "false")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_settings_accept_paper_only_true(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    get_settings.cache_clear()
    s = get_settings()
    assert s.alpaca_paper_only is True
