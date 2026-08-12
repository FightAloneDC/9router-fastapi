"""Serve Vite production build from app/static."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / "static"
_MISSING_DETAIL = (
    "UI not released. Run scripts/release-prod.sh"
)
# When OpenAPI UI is disabled, do not let SPA swallow these paths.
_RESERVED_PREFIXES = (
    "docs",
    "redoc",
    "openapi.json",
)


def prefers_html(accept: str) -> bool:
    """True when the client prefers an HTML document (browser navigation).

    Axios sends application/json first; <img> sends image/* — both skip SPA.
    """
    if not accept:
        return False
    for raw in accept.split(","):
        media = raw.strip().split(";")[0].strip().lower()
        if not media:
            continue
        if media == "text/html":
            return True
        if media == "application/json":
            return False
        if media.startswith("image/"):
            return False
    return False


def is_spa_navigation_path(path: str) -> bool:
    """Paths that may collide with API routes but are UI pages on refresh."""
    if path.startswith("/api/") or path == "/api":
        return False
    if path.startswith("/v1/") or path == "/v1":
        return False
    if path.startswith("/assets/"):
        return False
    if path in ("/health", "/docs", "/redoc", "/openapi.json"):
        return False
    if path.startswith("/docs/") or path.startswith("/redoc/"):
        return False
    # Icons are real files, not React routes
    if path.startswith("/providers/") and path.endswith(".png"):
        return False
    return True


class SpaHtmlMiddleware:
    """Serve index.html for browser navigations before API routes run.

    Fixes refresh on /providers, /settings, etc. returning API 401 JSON.
    """

    def __init__(self, app: Callable, index_path: Path) -> None:
        self.app = app
        self.index_path = index_path

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope.get("method") == "GET"
            and self.index_path.is_file()
        ):
            path = scope.get("path") or "/"
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in (scope.get("headers") or [])
            }
            accept = headers.get("accept", "")
            if prefers_html(accept) and is_spa_navigation_path(path):
                await FileResponse(self.index_path)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


def mount_provider_icons(
    app: FastAPI,
    static_dir: Path | None = None,
) -> None:
    """Serve /providers/{id}.png from static before API routes.

    Frontend uses <img src="/providers/{id}.png">. Without this, the
    authenticated /providers/{conn_id} route returns 401 for icons.

    Path must keep the `.png` suffix so /providers/client etc. still
    reach the API routers.
    """
    root = static_dir or STATIC_DIR
    icons = root / "providers"
    if not icons.is_dir():
        return

    @app.get("/providers/{name}.png")
    async def provider_png(name: str):
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(status_code=404, detail="Not Found")
        path = icons / f"{name}.png"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(path)


def mount_static_ui(
    app: FastAPI,
    static_dir: Path | None = None,
) -> None:
    root = static_dir or STATIC_DIR
    index = root / "index.html"

    if not index.is_file():
        @app.get("/")
        async def ui_missing():
            raise HTTPException(
                status_code=503,
                detail=_MISSING_DETAIL,
            )
        return

    assets = root / "assets"
    if assets.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets),
            name="ui-assets",
        )

    @app.get("/")
    async def ui_index():
        return FileResponse(index)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        head = full_path.split("/", 1)[0]
        if head in _RESERVED_PREFIXES:
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = root / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    # Outermost for these requests: browser refresh must not hit API 401.
    app.add_middleware(SpaHtmlMiddleware, index_path=index)
