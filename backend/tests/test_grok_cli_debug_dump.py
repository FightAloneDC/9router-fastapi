"""Tests for grok-cli client/response file dumps."""

from __future__ import annotations

import json
from pathlib import Path

from app.providers.grok_cli.debug_dump import (
    ChatSseAssembler,
    begin_dump,
    dump_enabled,
    finish_dump,
    parse_upstream_body,
    response_from_chat_completion,
)
from app.providers.grok_cli.stream import ResponsesUpstreamTranslator


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def test_dump_disabled_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GROK_CLI_DUMP", raising=False)
    monkeypatch.setenv("GROK_CLI_DUMP_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.providers.grok_cli.debug_dump._dotenv_value",
        lambda _name: None,
    )
    assert dump_enabled() is False
    assert begin_dump(
        request_id="rid-0",
        endpoint="/v1/chat/completions",
        stream=True,
        client_request={"model": "grok-4.6"},
        upstream_request={"model": "grok-4.6"},
    ) is None
    assert list(tmp_path.iterdir()) == []


def test_commented_dotenv_line_is_off(monkeypatch) -> None:
    monkeypatch.delenv("GROK_CLI_DUMP", raising=False)
    monkeypatch.setattr(
        "app.providers.grok_cli.debug_dump._dotenv_value",
        lambda _name: None,
    )
    assert dump_enabled() is False


def test_dump_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROK_CLI_DUMP", "0")
    monkeypatch.setenv("GROK_CLI_DUMP_DIR", str(tmp_path))
    assert dump_enabled() is False
    session = begin_dump(
        request_id="rid-1",
        endpoint="/v1/chat/completions",
        stream=True,
        client_request={"model": "grok-4.6"},
        upstream_request={"model": "grok-4.6"},
    )
    assert session is None
    assert list(tmp_path.iterdir()) == []


def test_begin_and_finish_writes_paired_files(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("GROK_CLI_DUMP", "1")
    monkeypatch.setenv("GROK_CLI_DUMP_DIR", str(tmp_path))
    session = begin_dump(
        request_id="abc-1234567890",
        endpoint="/v1/chat/completions",
        stream=True,
        client_request={
            "model": "gcli/grok-4.6",
            "messages": [{"role": "user", "content": "hi"}],
            "accessToken": "secret-token",
        },
        upstream_request={"model": "grok-4.6", "input": []},
        model="gcli/grok-4.6",
        connection_id="conn-1",
    )
    assert session is not None
    assert session.client_path.is_file()
    client = json.loads(session.client_path.read_text())
    assert client["client_request"]["accessToken"] == "[redacted]"
    assert client["client_request"]["messages"][0]["content"] == "hi"
    assert client["upstream_request"]["model"] == "grok-4.6"
    assert client["meta"]["stream"] is True

    finish_dump(
        session,
        {
            "content": "I will write the file",
            "reasoning_content": "thinking",
            "tool_calls": [{
                "id": "fc_1",
                "type": "function",
                "function": {
                    "name": "Write",
                    "arguments": '{"path":"x.md"}',
                },
            }],
            "finish_reason": "tool_calls",
            "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            "chunk_count": 3,
        },
        status="ok",
    )
    response = json.loads(session.response_path.read_text())
    assert response["meta"]["tool_call_names"] == ["Write"]
    assert response["meta"]["content_chars"] == len(
        "I will write the file",
    )
    assert response["response"]["finish_reason"] == "tool_calls"
    assert response["error"] is None


def test_finish_dump_never_raises(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("GROK_CLI_DUMP_DIR", str(tmp_path))
    finish_dump(None, {"content": "x"})


def test_parse_upstream_body_prefers_raw() -> None:
    raw = json.dumps({"model": "grok-4.6", "input": []}).encode()
    parsed = parse_upstream_body(raw, {"model": "other"})
    assert parsed == {"model": "grok-4.6", "input": []}


def test_response_from_chat_completion() -> None:
    out = response_from_chat_completion({
        "id": "chatcmpl-1",
        "model": "grok-4.6",
        "choices": [{
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "done",
                "reasoning_content": "why",
            },
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    })
    assert out["content"] == "done"
    assert out["reasoning_content"] == "why"
    assert out["finish_reason"] == "stop"
    assert out["usage"]["completion_tokens"] == 2


def test_assembler_rebuilds_text_reasoning_and_tools() -> None:
    translator = ResponsesUpstreamTranslator(model="grok-4.6")
    assembler = ChatSseAssembler()

    events = translator.feed(_sse({
        "type": "response.created",
        "response": {"id": "resp_1"},
    }))
    for ev in events:
        assembler.feed(ev)

    events = translator.feed(_sse({
        "type": "response.reasoning_summary_text.delta",
        "delta": "plan ",
    }))
    for ev in events:
        assembler.feed(ev)
    events = translator.feed(_sse({
        "type": "response.reasoning_summary_text.delta",
        "delta": "step",
    }))
    for ev in events:
        assembler.feed(ev)

    events = translator.feed(_sse({
        "type": "response.output_text.delta",
        "delta": "Hello ",
    }))
    for ev in events:
        assembler.feed(ev)
    events = translator.feed(_sse({
        "type": "response.output_text.delta",
        "delta": "world",
    }))
    for ev in events:
        assembler.feed(ev)

    events = translator.feed(_sse({
        "type": "response.output_item.added",
        "item": {
            "type": "function_call",
            "id": "fc_9",
            "call_id": "fc_9",
            "name": "Write",
        },
    }))
    for ev in events:
        assembler.feed(ev)
    events = translator.feed(_sse({
        "type": "response.function_call_arguments.delta",
        "item_id": "fc_9",
        "delta": '{"path":"AUDIT.md"}',
    }))
    for ev in events:
        assembler.feed(ev)

    events = translator.feed(_sse({
        "type": "response.completed",
        "response": {
            "status": "completed",
            "usage": {"input_tokens": 8, "output_tokens": 5},
        },
    }))
    for ev in events:
        assembler.feed(ev)

    result = assembler.to_dict()
    assert result["content"] == "Hello world"
    assert result["reasoning_content"] == "plan step"
    assert result["finish_reason"] == "tool_calls"
    assert result["tool_calls"][0]["function"]["name"] == "Write"
    assert result["tool_calls"][0]["function"]["arguments"] == (
        '{"path":"AUDIT.md"}'
    )
    assert result["usage"]["prompt_tokens"] == 8
    assert result["usage"]["completion_tokens"] == 5
