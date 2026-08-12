"""Rewrite /api/* to /* for same-origin dashboard calls."""

from __future__ import annotations

from typing import Callable


class StripApiPrefixMiddleware:
    """ASGI middleware: strip leading /api for HTTP and WebSocket."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path") or ""
            if path == "/api" or path.startswith("/api/"):
                new_path = path[4:] or "/"
                scope = dict(scope)
                scope["path"] = new_path
        await self.app(scope, receive, send)
