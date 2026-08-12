"""Serve built UI from app/static with SPA fallback."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.openapi_ui import openapi_ui_kwargs
from app.static_ui import mount_provider_icons, mount_static_ui


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


def test_provider_png_served_before_api_route(tmp_path: Path):
    icons = tmp_path / "providers"
    icons.mkdir()
    (icons / "grok-cli.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    app = FastAPI()
    mount_provider_icons(app, tmp_path)

    @app.get("/providers/client")
    async def client_list():
        return {"ok": True}

    @app.get("/providers/{conn_id}")
    async def get_conn(conn_id: str):
        return {"id": conn_id, "auth": True}

    client = TestClient(app)
    icon = client.get("/providers/grok-cli.png")
    assert icon.status_code == 200
    assert icon.content.startswith(b"\x89PNG")
    # Non-png provider API paths must not be stolen by icon route
    assert client.get("/providers/client").json() == {"ok": True}
    assert client.get("/providers/some-uuid").json()["id"] == "some-uuid"
