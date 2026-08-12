"""Strip /api prefix for same-origin UI clients."""

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app.middleware.api_prefix import StripApiPrefixMiddleware


def _app_with_middleware() -> FastAPI:
    app = FastAPI()
    app.add_middleware(StripApiPrefixMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/auth/status")
    async def auth_status():
        return {"ok": True}

    @app.websocket("/console/ws")
    async def console_ws(ws: WebSocket):
        await ws.accept()
        await ws.send_text("pong")
        await ws.close()

    return app


def test_api_prefix_rewrites_http():
    client = TestClient(_app_with_middleware())
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/status").json() == {"ok": True}


def test_bare_paths_still_work():
    client = TestClient(_app_with_middleware())
    assert client.get("/health").json() == {"status": "ok"}


def test_v1_not_stripped_as_api():
    """Path /v1 must not be treated as /api strip target."""
    app = _app_with_middleware()

    @app.get("/v1/chat/completions")
    async def chat():
        return {"object": "chat"}

    client = TestClient(app)
    assert client.get("/v1/chat/completions").status_code == 200
    assert client.get("/v1/chat/completions").json()["object"] == "chat"


def test_api_prefix_rewrites_websocket():
    client = TestClient(_app_with_middleware())
    with client.websocket_connect("/api/console/ws") as ws:
        assert ws.receive_text() == "pong"
