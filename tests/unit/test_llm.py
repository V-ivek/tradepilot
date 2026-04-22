from pydantic import SecretStr

from src.config.settings import get_settings
from src.services.llm import get_agent_model, get_chat_model, get_guard_model


def _set_required_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")


def _get_api_key(model):
    key = getattr(model, "openai_api_key", None) or getattr(model, "api_key", None)
    if isinstance(key, SecretStr):
        return key.get_secret_value()
    return key


def _get_base_url(model):
    return getattr(model, "openai_api_base", None) or getattr(model, "base_url", None)


def test_get_guard_model_uses_guard_model_name_and_litellm(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm:4000/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-dev")
    monkeypatch.setenv("GUARD_MODEL", "claude-haiku-4-5")
    get_settings.cache_clear()

    m = get_guard_model()

    assert m.model_name == "claude-haiku-4-5"
    assert str(_get_base_url(m)).rstrip("/") == "http://litellm:4000/v1"
    assert _get_api_key(m) == "sk-dev"
    assert m.temperature == 0


def test_get_agent_model_uses_agent_model_name(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("AGENT_MODEL", "claude-sonnet-4-5")
    get_settings.cache_clear()

    m = get_agent_model()

    assert m.model_name == "claude-sonnet-4-5"


def test_get_chat_model_uses_named_model(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x/v1")
    get_settings.cache_clear()

    m = get_chat_model("gpt-4o")

    assert m.model_name == "gpt-4o"
