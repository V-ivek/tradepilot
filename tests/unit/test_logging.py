import io
import json
import logging

import structlog

from src.observability.logging import configure_logging, get_logger


def test_get_logger_returns_bound_logger():
    configure_logging()
    log = get_logger("tradepilot.test")
    assert isinstance(log, structlog.stdlib.BoundLogger)


def test_json_renderer_includes_timestamp_and_level(capsys):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    prev_handlers = list(root.handlers)
    prev_level = root.level
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    try:
        configure_logging()
        log = get_logger("tradepilot.render-test")
        log.info("hello", foo="bar")
        line = buf.getvalue().strip().splitlines()[-1]
        payload = json.loads(line)
    finally:
        root.handlers = prev_handlers
        root.setLevel(prev_level)

    assert payload["event"] == "hello"
    assert payload["foo"] == "bar"
    assert payload["level"] == "info"
    assert "timestamp" in payload
    assert payload["logger"] == "tradepilot.render-test"
