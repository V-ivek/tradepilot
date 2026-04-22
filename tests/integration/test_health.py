from fastapi.testclient import TestClient

from src.config.settings import get_settings


def _set_required_env(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_ONLY", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://x")


def test_health_reports_paper_mode(monkeypatch):
    _set_required_env(monkeypatch)
    get_settings.cache_clear()
    from src.main import create_app

    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["trading_mode"] == "paper"
