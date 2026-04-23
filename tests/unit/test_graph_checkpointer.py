from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver

from src.agent.graph import default_checkpointer


def test_no_database_url_returns_memory_saver():
    saver = default_checkpointer(None)
    assert isinstance(saver, MemorySaver)


def test_empty_database_url_returns_memory_saver():
    saver = default_checkpointer("")
    assert isinstance(saver, MemorySaver)


def test_database_url_uses_postgres_saver_when_available():
    """If the PostgresSaver import succeeds, the helper calls its factory."""

    class _FakePostgresSaver:
        @classmethod
        def from_conn_string(cls, url):
            cls.last_url = url
            return object()

    module = type("_Mod", (), {"PostgresSaver": _FakePostgresSaver})
    with patch.dict(
        "sys.modules",
        {"langgraph.checkpoint.postgres": module},
    ):
        saver = default_checkpointer("postgresql://x")

    assert _FakePostgresSaver.last_url == "postgresql://x"
    assert saver is not None


def test_postgres_import_failure_falls_back_to_memory():
    def _raise_import(*args, **kwargs):
        raise ImportError("no module")

    with (
        patch(
            "src.agent.graph.default_checkpointer.__globals__",
            {},
        ),
        patch.dict("sys.modules", {"langgraph.checkpoint.postgres": None}),
    ):
        saver = default_checkpointer("postgresql://x")

    assert isinstance(saver, MemorySaver)
