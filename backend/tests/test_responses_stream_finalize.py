"""Tests for Responses API stream terminal-event finalize."""

from __future__ import annotations

import json

from app.services.responses_translator import (
    ResponsesStreamTranslator,
    build_incomplete_terminal_sse,
)


def test_chat_to_responses_finalize_without_finish_reason():
    t = ResponsesStreamTranslator(model="gpt-test")
    events = t.translate_chunk({
        "id": "chatcmpl-1",
        "created": 1,
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant", "content": "Hi"},
            "finish_reason": None,
        }],
    })
    assert any(e["event"] == "response.created" for e in events)
    assert not any(e["event"] == "response.completed" for e in events)

    final = t.finalize()
    assert final, "finalize() must emit terminal Responses events"
    assert final[-1]["event"] == "response.completed"
    assert final[-1]["data"]["type"] == "response.completed"
    assert t.finalize() == []


def test_chat_to_responses_finalize_noop_after_finish_reason():
    t = ResponsesStreamTranslator(model="gpt-test")
    t.translate_chunk({
        "id": "chatcmpl-1",
        "created": 1,
        "choices": [{
            "index": 0,
            "delta": {"content": "Hi"},
            "finish_reason": None,
        }],
    })
    t.translate_chunk({
        "id": "chatcmpl-1",
        "created": 1,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    })
    assert t.finalize() == []


def test_build_incomplete_terminal_sse_is_terminal_event():
    raw = build_incomplete_terminal_sse(
        response_id="resp_x",
        model="grok-4.5",
    )
    assert "event: response.incomplete\n" in raw
    assert "data: " in raw
    data_line = [
        line for line in raw.split("\n") if line.startswith("data: ")
    ][0]
    payload = json.loads(data_line[6:])
    assert payload["type"] == "response.incomplete"
    assert payload["response"]["id"] == "resp_x"
    assert payload["response"]["status"] == "incomplete"


def test_chat_to_responses_streams_tool_calls_and_fills_completed_output():
    """Tool calls must stream + appear in response.completed.output."""
    t = ResponsesStreamTranslator(model="gpt-test")
    events: list[dict] = []
    events.extend(t.translate_chunk({
        "id": "chatcmpl-1",
        "created": 1,
        "choices": [{
            "index": 0,
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "list_files", "arguments": ""},
                }],
            },
            "finish_reason": None,
        }],
    }))
    events.extend(t.translate_chunk({
        "id": "chatcmpl-1",
        "created": 1,
        "choices": [{
            "index": 0,
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "function": {"arguments": "{\"path\":\".\"}"},
                }],
            },
            "finish_reason": None,
        }],
    }))
    events.extend(t.translate_chunk({
        "id": "chatcmpl-1",
        "created": 1,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "tool_calls",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }))

    types = [e["event"] for e in events]
    assert "response.output_item.added" in types
    assert "response.function_call_arguments.delta" in types
    assert "response.output_item.done" in types
    assert types[-1] == "response.completed"
    completed = events[-1]["data"]["response"]
    assert completed["output"], "completed.output must include function_call"
    assert completed["output"][0]["type"] == "function_call"
    assert completed["output"][0]["name"] == "list_files"
    assert completed["output"][0]["arguments"] == "{\"path\":\".\"}"
