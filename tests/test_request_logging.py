import json
import logging
from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

import anyio

from codex_autorunner.web.middleware import RequestIdMiddleware


def _make_buffer_logger() -> tuple[logging.Logger, StringIO, logging.Handler]:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger(f"test.request_logging.{uuid4()}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    return logger, stream, handler


class _DummyApp:
    def __init__(self, logger: logging.Logger) -> None:
        self.state = SimpleNamespace(logger=logger)

    async def __call__(self, scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})


def test_request_logs_exclude_query_string_token() -> None:
    logger, stream, handler = _make_buffer_logger()
    app = _DummyApp(logger)
    middleware = RequestIdMiddleware(app)

    async def _run():
        scope = {
            "type": "http",
            "path": "/api/terminal",
            "query_string": b"token=secret",
            "headers": [],
            "method": "GET",
            "scheme": "http",
            "http_version": "1.1",
            "client": ("127.0.0.1", 12345),
            "app": app,
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await middleware(scope, receive, send)

    anyio.run(_run)
    handler.flush()

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert lines
    for line in lines:
        assert "token=secret" not in line
        payload = json.loads(line)
        assert payload["path"] == "/api/terminal"
