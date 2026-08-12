"""Serve Vite production build from app/static."""

from __future__ import annotations

from pathlib import Path

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
