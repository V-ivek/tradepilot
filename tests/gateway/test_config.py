from gateway.config import GatewaySettings, get_settings


def test_gateway_settings_defaults(monkeypatch):
    # Hermetic: ignore any local .env and OS env so we test true defaults.
    for var in (
        "ALPACA_API_KEY_ID",
        "ALPACA_API_SECRET_KEY",
        "FINNHUB_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "ALPACA_PAPER_ONLY",
    ):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    s = GatewaySettings(_env_file=None)
    assert s.alpaca_paper_only is True
    assert s.finnhub_api_key == ""
    assert s.alpaca_api_key_id == ""


def test_gateway_settings_reads_env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "abc")
    monkeypatch.setenv("FINNHUB_API_KEY", "xyz")
    get_settings.cache_clear()
    s = get_settings()
    assert s.alpaca_api_key_id == "abc"
    assert s.finnhub_api_key == "xyz"
