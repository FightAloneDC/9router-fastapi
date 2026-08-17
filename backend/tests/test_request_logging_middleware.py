"""Quiet SQLAlchemy pool terminate on client disconnect cancel."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import (
    IgnorePoolTerminateCancel,
    install_quiet_pool_terminate,
)
from app.middleware.request_logging import RequestLoggingMiddleware
from sqlalchemy.pool.base import Pool


def test_request_logging_middleware_logs_status() -> None:
    logs: list[dict] = []

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({"type": "http.response.body", "body": b"ok"})

    import app.routers.console as console

    original = console.add_log

    def capture(**kwargs):
        logs.append(kwargs)

    console.add_log = capture  # type: ignore[assignment]
    try:
        mw = RequestLoggingMiddleware(app)
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "path": "/health",
            "raw_path": b"/health",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 9000),
            "scheme": "http",
        }

        async def receive():
            return {"type": "http.disconnect"}

        sent: list[dict] = []

        async def send(message):
            sent.append(message)

        asyncio.run(mw(scope, receive, send))
    finally:
        console.add_log = original  # type: ignore[assignment]

    assert any(m["type"] == "http.response.start" for m in sent)
    assert logs
    assert logs[0]["level"] == "INFO"
    assert "GET /health -> 200" in logs[0]["message"]


def test_get_db_shields_close_on_cancel() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    with patch("app.database.async_session", return_value=session):
        from app.database import get_db

        async def _run() -> None:
            gen = get_db()
            await gen.__anext__()
            with pytest.raises(asyncio.CancelledError):
                await gen.athrow(asyncio.CancelledError())

        asyncio.run(_run())

    session.rollback.assert_awaited()
    session.close.assert_awaited()


def test_pool_terminate_cancel_filter() -> None:
    filt = IgnorePoolTerminateCancel()
    rec = logging.LogRecord(
        name="sqlalchemy.pool.AsyncAdaptedQueuePool",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Exception terminating connection %s",
        args=("conn",),
        exc_info=(asyncio.CancelledError, asyncio.CancelledError(), None),
    )
    assert filt.filter(rec) is False

    ok = logging.LogRecord(
        name="sqlalchemy.pool.AsyncAdaptedQueuePool",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Exception terminating connection %s",
        args=("conn",),
        exc_info=(RuntimeError, RuntimeError("boom"), None),
    )
    assert filt.filter(ok) is True


def test_quiet_pool_close_skips_log_on_cancel() -> None:
    install_quiet_pool_terminate()
    assert getattr(Pool._close_connection, "_9router_quiet", False)

    class _FakePool:
        logger = MagicMock()
        _dialect = MagicMock()

        def __init__(self) -> None:
            self._dialect.do_terminate.side_effect = (
                asyncio.CancelledError()
            )

    pool = _FakePool()
    with pytest.raises(asyncio.CancelledError):
        Pool._close_connection(pool, object(), terminate=True)
    pool.logger.error.assert_not_called()
