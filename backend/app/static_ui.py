"""Serve Vite production build from app/static."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
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

# Static provider id → existing icon basename (no .png).
# Dynamic node ids (openai-compatible-*) use prefix rules below.
_ICON_ALIASES: dict[str, str] = {
    "gitlab": "github",
    "keelcode": "kilocode",
    "kilo-gateway": "kilocode",
    "amazon-bedrock": "aws-polly",
    "bedrock": "aws-polly",
}

# Tiny transparent 1×1 PNG — last resort so <img> does not 404.
_TRANSPARENT_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
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


def resolve_provider_icon(
    icons_dir: Path, name: str,
) -> Path | None:
    """Resolve provider id to an icon file under *icons_dir*.

    Order: exact file → static alias → compatible-node prefix → None.
    """
    exact = icons_dir / f"{name}.png"
    if exact.is_file():
        return exact

    alias = _ICON_ALIASES.get(name)
    if alias:
        aliased = icons_dir / f"{alias}.png"
        if aliased.is_file():
            return aliased

    # Custom OpenAI/Anthropic-compatible nodes: id is
    # openai-compatible-chat-<hash> / anthropic-compatible-<hash>
    if name.startswith("openai-compatible"):
        openai = icons_dir / "openai.png"
        if openai.is_file():
            return openai
    if name.startswith("anthropic-compatible"):
        anthropic = icons_dir / "anthropic.png"
        if anthropic.is_file():
            return anthropic

    return None


def mount_provider_icons(
    app: FastAPI,
    static_dir: Path | None = None,
) -> None:
    """Serve /providers/{id}.png from static before API routes.

    Frontend uses <img src="/providers/{id}.png">. Without this, the
    authenticated /providers/{conn_id} route returns 401 for icons.

    Path must keep the `.png` suffix so /providers/client etc. still
    reach the API routers. Missing brand icons fall back via
    resolve_provider_icon (aliases / compatible-node prefix) so the
    Providers page does not spam 404s in the browser console.
    """
    root = static_dir or STATIC_DIR
    icons = root / "providers"
    if not icons.is_dir():
        return

    @app.get("/providers/{name}.png")
    async def provider_png(name: str):
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(status_code=404, detail="Not Found")
        path = resolve_provider_icon(icons, name)
        if path is not None:
            return FileResponse(path)
        # Avoid console 404 noise for unknown catalog ids; 1×1 PNG.
        return Response(
            content=_TRANSPARENT_PNG,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )


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
