"""ChatOpenAI wrappers pointed at the local LiteLLM proxy.

LiteLLM speaks the OpenAI wire format; every model (Claude, GPT, Gemini, etc.)
is routed by ``model_name`` so the agent code stays provider-agnostic.
"""

from langchain_openai import ChatOpenAI

from src.config.settings import Settings, get_settings


def _build(model: str, settings: Settings, **overrides) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        **overrides,
    )


def get_chat_model(name: str, **overrides) -> ChatOpenAI:
    """Get an arbitrary chat model by LiteLLM model name."""
    return _build(name, get_settings(), **overrides)


def get_guard_model(**overrides) -> ChatOpenAI:
    """Cheap, fast model used by the guard and confirmation-classifier nodes."""
    s = get_settings()
    return _build(s.guard_model, s, temperature=0, **overrides)


def get_agent_model(**overrides) -> ChatOpenAI:
    """Default specialist-agent model."""
    s = get_settings()
    return _build(s.agent_model, s, **overrides)
