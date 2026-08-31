"""HTTP request logging without BaseHTTPMiddleware cancel bugs."""

from __future__ import annotations

import time
from typing import Callable

from app.routers import console


class RequestLoggingMiddleware:
    """Pure ASGI request logger for the console buffer.

    ``@app.middleware("http")`` uses Starlette BaseHTTPMiddleware, which
    runs the app in a child task and cancels it on client disconnect.
    That cancel hits SQLAlchemy/asyncpg pool ``terminate`` and logs a
    scary ``Exception terminating connection`` / ``CancelledError``.
    Pure ASGI avoids that cancel scope.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        status_code = 500
        path = scope.get("path") or ""
        method = scope.get("method") or "?"

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Still log; re-raise so FastAPI error handling runs.
            self._log(method, path, status_code, start)
            raise
        self._log(method, path, status_code, start)

    @staticmethod
    def _log(
        method: str, path: str, status: int, start: float,
    ) -> None:
        duration_ms = round((time.time() - start) * 1000, 1)
        level = (
            "ERROR" if status >= 500
            else "WARN" if status >= 400
            else "INFO"
        )
        console.add_log(
            level=level,
            message=(
                f"{method} {path} -> {status} ({duration_ms}ms)"
            ),
            source="http",
        )
