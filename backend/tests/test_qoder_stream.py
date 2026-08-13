"""Regression tests: Qoder SSE relay must survive chunk-boundary splits.

Bug: ``_stream_response()`` decoded each httpx read independently and
split it on newlines without carrying partial lines over to the next
read. An SSE line split across two reads was dropped entirely, losing
tool-call argument deltas (corrupted/empty arguments) and text deltas
(mangled strings). See docs/TOOL-CALLING-CORRUPTION.md.

The fake upstream below writes the wrapped SSE payload in small,
delayed pieces so lines are reliably split across reads.
"""

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.routers.v1_proxy.shared import (
    ProxyTarget,
    _capture_qoder_usage,
    _stream_response,
    _unwrap_qoder_sse_line,
)

EXPECTED_ARGS = {
    "command": "ls -la . docs/reference tests",
    "timeout": 60,
}


def _wrap(openai_chunk: dict | str) -> str:
    """Wrap one OpenAI chunk in the Qoder SSE envelope."""
    body = openai_chunk if isinstance(openai_chunk, str) else (
        json.dumps(openai_chunk)
    )
    envelope = {"statusCodeValue": 200, "body": body}
    return f"data: {json.dumps(envelope)}\n\n"


def _tool_chunks() -> list[str]:
    """OpenAI chunks for one Bash tool call, args split in 3 deltas."""
    args = json.dumps(EXPECTED_ARGS)
    third = len(args) // 3
    fragments = [args[:third], args[third:2 * third], args[2 * third:]]
    chunks = [{
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "qoder/kmodel_latest",
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant", "tool_calls": [{
                "index": 0,
                "id": "call_1",
                "type": "function",
                "function": {"name": "Bash", "arguments": ""},
            }]},
        }],
    }]
    for frag in fragments:
        chunks.append({
            "id": "chatcmpl-test",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "qoder/kmodel_latest",
            "choices": [{
                "index": 0,
                "delta": {"tool_calls": [{
                    "index": 0,
                    "function": {"arguments": frag},
                }]},
            }],
        })
    chunks.append({
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "qoder/kmodel_latest",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 7, "completion_tokens": 11,
            "total_tokens": 18,
        },
    })
    return chunks


class _SplittingHandler(BaseHTTPRequestHandler):
    """Serves the wrapped SSE payload in small delayed pieces.

    ``pieces`` (class attr) is the list of raw byte pieces to write;
    each piece is flushed separately with a short sleep so the client
    observes them as separate reads.
    """

    pieces: list[bytes] = []

    def do_POST(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in self.pieces:
            self.wfile.write(piece)
            self.wfile.flush()
            time.sleep(0.005)

    def log_message(self, *args):  # silence request logging
        pass


def _start_server(payload: bytes, piece_size: int) -> tuple[
    ThreadingHTTPServer, str
]:
    pieces = [
        payload[i:i + piece_size] for i in range(0, len(payload), piece_size)
    ]

    class Handler(_SplittingHandler):
        pass

    Handler.pieces = pieces
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}/chat"


def _run_stream(url: str) -> str:
    """POST a streaming chat request through _stream_response."""
    target = ProxyTarget()
    target.url = url
    target.headers = {}
    target.model = "qoder/kmodel_latest"
    # Fake provider id: skips handler lookup, exercises only the relay.
    target.provider = "fake-provider"
    target.connection_id = None

    async def collect() -> str:
        resp = await _stream_response(
            target, {"model": "qd/qoder/kmodel_latest", "stream": True},
            "req-test", provider="qoder", model="qoder/kmodel_latest",
        )
        parts: list[str] = []
        async for piece in resp.body_iterator:
            parts.append(
                piece.decode("utf-8") if isinstance(piece, bytes) else piece
            )
        return "".join(parts)

    return asyncio.run(collect())


def _parse_events(raw: str) -> list[dict]:
    events = []
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[6:]))
    return events


def _reassemble(events: list[dict]) -> tuple[str, str, str | None]:
    """Return (tool_name, arguments_json, finish_reason) from chunks."""
    name = ""
    args = ""
    finish = None
    for ev in events:
        choice = (ev.get("choices") or [{}])[0]
        delta = choice.get("delta", {})
        for tc in delta.get("tool_calls", []):
            fn = tc.get("function", {})
            if fn.get("name"):
                name = fn["name"]
            args += fn.get("arguments", "")
        if choice.get("finish_reason"):
            finish = choice["finish_reason"]
    return name, args, finish


def test_qoder_stream_tool_args_survive_line_splits():
    payload = "".join(_wrap(c) for c in _tool_chunks()).encode()
    payload += _wrap("[DONE]").encode()
    # 17-byte pieces: every SSE line is split across multiple reads.
    server, url = _start_server(payload, piece_size=17)
    try:
        raw = _run_stream(url)
    finally:
        server.shutdown()

    events = _parse_events(raw)
    name, args, finish = _reassemble(events)
    assert name == "Bash"
    assert finish == "stop"
    assert json.loads(args) == EXPECTED_ARGS
    # Usage of the final chunk must survive too.
    usage = events[-1].get("usage") or events[-2].get("usage")
    assert usage and usage["completion_tokens"] == 11


def test_qoder_stream_multibyte_text_survive_splits():
    text = "h\u00e9llo \u2713 d\u00fcni\u00e4"  # héllo ✓ düniä
    chunk = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "qoder/kmodel_latest",
        "choices": [{"index": 0, "delta": {"content": text}}],
    }
    payload = (_wrap(chunk) + _wrap("[DONE]")).encode()
    # 13-byte pieces: splits land inside multi-byte UTF-8 sequences.
    server, url = _start_server(payload, piece_size=13)
    try:
        raw = _run_stream(url)
    finally:
        server.shutdown()

    events = _parse_events(raw)
    got = "".join(
        (ev.get("choices") or [{}])[0].get("delta", {}).get("content", "")
        for ev in events
    )
    assert got == text


def test_qoder_stream_final_line_without_trailing_newline():
    payload = "".join(_wrap(c) for c in _tool_chunks()).encode()
    payload += _wrap("[DONE]").encode()
    payload = payload.rstrip(b"\n")  # no trailing newline at all
    server, url = _start_server(payload, piece_size=29)
    try:
        raw = _run_stream(url)
    finally:
        server.shutdown()

    events = _parse_events(raw)
    _, args, _ = _reassemble(events)
    assert json.loads(args) == EXPECTED_ARGS
    assert raw.rstrip().endswith("data: [DONE]")


# ── Unit tests: line unwrapper + usage capture ─────────────────────────


def test_unwrap_qoder_sse_line_formats():
    chunk = {"choices": [{"index": 0, "delta": {"content": "hi"}}]}
    # New format: {"headers": ..., "body": ...}
    new = "data: " + json.dumps(
        {"headers": {"x": "1"}, "body": json.dumps(chunk)}
    )
    assert json.loads(_unwrap_qoder_sse_line(new)[6:]) == chunk
    # Old format: {"statusCodeValue": 200, "body": ...}
    old = "data: " + json.dumps(
        {"statusCodeValue": 200, "body": json.dumps(chunk)}
    )
    assert json.loads(_unwrap_qoder_sse_line(old)[6:]) == chunk
    # [DONE] passthrough
    done = "data: " + json.dumps({"statusCodeValue": 200, "body": "[DONE]"})
    assert _unwrap_qoder_sse_line(done) == "data: [DONE]"
    # Direct OpenAI chunk (no envelope)
    direct = "data: " + json.dumps(chunk)
    assert json.loads(_unwrap_qoder_sse_line(direct)[6:]) == chunk
    # Garbage / non-data lines are skipped
    assert _unwrap_qoder_sse_line("data: not-json") is None
    assert _unwrap_qoder_sse_line(": keepalive") is None
    assert _unwrap_qoder_sse_line("") is None


def test_unwrap_qoder_code_112_quota_envelope():
    """Bare code/message envelopes must become [qoder error ...] markers."""
    from app.providers.qoder.transform import qoder_envelope_http_error

    env = {
        "code": "112",
        "message": json.dumps({
            "pricingUrl": "https://qoder.com/pricing?client=qoder",
        }),
    }
    st, detail = qoder_envelope_http_error(env)
    assert st == 402
    assert "pricing" in detail.lower() or "112" in detail

    line = "data: " + json.dumps(env)
    unwrapped = _unwrap_qoder_sse_line(line)
    assert unwrapped is not None
    payload = json.loads(unwrapped[6:])
    content = payload["choices"][0]["delta"]["content"]
    assert "[qoder error 402:" in content.lstrip()
    assert "112" in content or "pricing" in content.lower()

    # Nested inside statusCodeValue/body (seen on live streams)
    nested = "data: " + json.dumps({
        "statusCodeValue": 200,
        "body": json.dumps(env),
    })
    unwrapped2 = _unwrap_qoder_sse_line(nested)
    assert unwrapped2 is not None
    content2 = json.loads(unwrapped2[6:])["choices"][0]["delta"]["content"]
    assert "[qoder error 402:" in content2.lstrip()


def test_capture_qoder_usage():
    cur = {"prompt_tokens": 1}
    line = "data: " + json.dumps({"usage": {"prompt_tokens": 9}})
    assert _capture_qoder_usage(line, cur)["prompt_tokens"] == 9
    assert _capture_qoder_usage("data: [DONE]", cur) is cur
    assert _capture_qoder_usage("data: {}", cur) is cur
    assert _capture_qoder_usage("data: bad-json", cur) is cur


def test_qoder_business_error_raises_before_stream():
    """code:112 on first SSE event must raise HTTPStatusError (fallback)."""
    payload = (
        "data: "
        + json.dumps({
            "code": "112",
            "message": json.dumps({
                "pricingUrl": "https://qoder.com/pricing?client=qoder",
            }),
        })
        + "\n\n"
    ).encode()
    server, url = _start_server(payload, piece_size=64)
    try:
        target = ProxyTarget()
        target.url = url
        target.headers = {}
        target.model = "qoder/auto"
        target.provider = "fake-provider"
        target.connection_id = None

        async def run() -> None:
            await _stream_response(
                target,
                {"model": "qd/qoder/auto", "stream": True},
                "req-quota",
                provider="qoder",
                model="qoder/auto",
            )

        import httpx
        import pytest

        with pytest.raises(httpx.HTTPStatusError) as ei:
            asyncio.run(run())
        assert ei.value.response.status_code == 402
    finally:
        server.shutdown()
