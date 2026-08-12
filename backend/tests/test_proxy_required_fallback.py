"""Regression tests for strict proxy failures in v1 fallback loops."""

import asyncio
import json
from types import SimpleNamespace

from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.routers.v1_proxy import chat, messages
from app.services.outbound_proxy import ProxyRequiredError


def _request(body: dict) -> Request:
    """Create an ASGI request with a JSON body."""

    async def receive() -> dict:
        return {
            "type": "http.request",
            "body": json.dumps(body).encode(),
        }

    return Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [],
        },
        receive,
    )


def _target(connection_id: str) -> SimpleNamespace:
    """Build a minimal resolved upstream target."""
    return SimpleNamespace(
        connection_id=connection_id,
        headers={},
        model="upstream-model",
        provider="unknown-provider",
        url="https://example.test/v1/chat/completions",
    )


def test_chat_retries_next_connection_after_strict_proxy_failure(monkeypatch):
    """A strict proxy failure excludes one chat connection and retries."""
    first = _target("first")
    second = _target("second")
    seen_excludes: list[set[str]] = []
    connection = SimpleNamespace(data="{}")

    class Db:
        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: connection)

    async def resolve(_db, _model, _stream, **kwargs):
        excludes = set(kwargs["exclude_ids"])
        seen_excludes.append(excludes)
        if not excludes:
            return [first]
        if excludes == {"first"}:
            return [second]
        return []

    async def resolve_proxy(_db, conn, _purpose):
        if conn is connection and len(seen_excludes) == 1:
            raise ProxyRequiredError("Proxy required")
        return None

    async def no_op(*_args, **_kwargs):
        return None

    async def response(*_args, **_kwargs):
        return JSONResponse(content={"ok": True}), {"usage": {}}

    monkeypatch.setattr(chat, "resolve_model_to_targets", resolve)
    monkeypatch.setattr(chat, "proxy_for_connection", resolve_proxy)
    monkeypatch.setattr(chat, "_non_stream_response", response)
    monkeypatch.setattr(chat, "clear_connection_error", no_op)
    monkeypatch.setattr(chat, "update_connection_usage", no_op)
    monkeypatch.setattr(chat, "save_request_tracking", no_op)
    monkeypatch.setattr(chat, "track_request_start", lambda *_args: "request")
    monkeypatch.setattr(chat, "track_request_end", lambda *_args, **_kwargs: None)

    async def strategy(*_args, **_kwargs):
        return "round-robin", 0

    monkeypatch.setattr(chat, "get_combo_strategy", strategy)
    result = asyncio.run(
        chat.chat_completions(
            _request({"model": "combo", "messages": [], "stream": False}),
            Db(),
            {},
        )
    )

    assert result.status_code == 200
    assert seen_excludes == [set(), {"first"}]


def test_messages_retries_next_connection_after_strict_proxy_failure(
    monkeypatch,
):
    """A strict proxy failure excludes one Messages connection and retries."""
    first = _target("first")
    second = _target("second")
    seen_excludes: list[set[str]] = []
    connection = SimpleNamespace(data="{}")

    class Db:
        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: connection)

    class UpstreamResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return UpstreamResponse()

    async def resolve(_db, _model, _stream, **kwargs):
        excludes = set(kwargs["exclude_ids"])
        seen_excludes.append(excludes)
        if not excludes:
            return [first]
        if excludes == {"first"}:
            return [second]
        return []

    async def resolve_proxy(_db, conn, _purpose):
        if conn is connection and len(seen_excludes) == 1:
            raise ProxyRequiredError("Proxy required")
        return None

    async def no_op(*_args, **_kwargs):
        return None

    async def strategy(*_args, **_kwargs):
        return "round-robin", 0

    def client_factory(**_kwargs):
        return Client()

    monkeypatch.setattr(messages, "get_combo_strategy", strategy)
    monkeypatch.setattr(messages, "resolve_model_to_targets", resolve)
    monkeypatch.setattr(messages, "proxy_for_connection", resolve_proxy)
    monkeypatch.setattr(messages, "create_upstream_client", client_factory)
    monkeypatch.setattr(
        messages,
        "openai_to_claude_response",
        lambda *_args, **_kwargs: {"type": "message"},
    )
    monkeypatch.setattr(messages, "clear_connection_error", no_op)
    monkeypatch.setattr(messages, "update_connection_usage", no_op)
    monkeypatch.setattr(messages, "save_request_tracking", no_op)
    monkeypatch.setattr(messages, "track_request_start", lambda *_args: "request")
    monkeypatch.setattr(messages, "track_request_end", lambda *_args, **_kwargs: None)

    result = asyncio.run(
        messages.messages_endpoint(
            _request(
                {
                    "model": "combo",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                }
            ),
            Db(),
            {},
        )
    )

    assert result.status_code == 200
    assert seen_excludes == [set(), {"first"}]
