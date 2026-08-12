"""Serve built UI from app/static with SPA fallback."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.openapi_ui import openapi_ui_kwargs
from app.static_ui import mount_static_ui


def test_missing_index_returns_clear_error(tmp_path: Path):
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    mount_static_ui(app, tmp_path)
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    res = client.get("/")
    assert res.status_code == 503
    assert "release-prod" in res.json()["detail"]


def test_serves_index_and_spa_fallback(tmp_path: Path):
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>9Router</title>",
        encoding="utf-8",
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text(
        "console.log(1)", encoding="utf-8"
    )

    # Mirror production: OpenAPI UI off → /docs must 404,
    # not be swallowed by SPA.
    app = FastAPI(**openapi_ui_kwargs(False))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models():
        return {"data": []}

    mount_static_ui(app, tmp_path)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/v1/models").json() == {"data": []}
    assert "9Router" in client.get("/").text
    assert "9Router" in client.get("/providers").text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
