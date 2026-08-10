"""Tests for the Grok CLI (Grok Build) provider transformation layer."""

import json

from app.providers.grok_cli import transform
from app.providers.grok_cli.stream import ResponsesUpstreamTranslator


# ── Request translation: Chat Completions -> Responses API ───────────────


def test_chat_to_responses_request_basic_messages():
    body = {
        "model": "grok-build",
        "messages": [
            {"role": "system", "content": "You are concise."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ],
    }
    result = transform.chat_to_responses_request(body)

    assert result["instructions"] == "You are concise."
    assert result["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Hello"}],
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "input_text", "text": "Hi there"}],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "How are you?"}],
        },
    ]


def test_chat_to_responses_request_tool_round_trip():
    body = {
        "messages": [
            {"role": "user", "content": "What is the weather?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": "{\"city\": \"Berlin\"}",
                    },
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "Sunny, 21C",
            },
        ],
    }
    result = transform.chat_to_responses_request(body)

    assert result["input"][0]["type"] == "message"
    assert result["input"][1] == {
        "type": "function_call",
        "call_id": "call_1",
        "name": "get_weather",
        "arguments": "{\"city\": \"Berlin\"}",
    }
    assert result["input"][2] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": "Sunny, 21C",
    }


def test_build_request_forces_stream_and_store_false():
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 100,
        "seed": 42,  # chat leftover — must be dropped
    }
    result, meta = transform.build_grok_cli_request(
        "grok-build", body, {"accessToken": "tok"},
    )

    assert result["stream"] is True
    assert result["store"] is False
    assert result["model"] == "grok-build"
    assert result["max_output_tokens"] == 100
    assert "seed" not in result
    assert "messages" not in result
    assert meta["sessionId"]
    assert meta["reqId"]
    assert meta["turnIdx"] == 1
    # grok-build does not support effort but gets summary + encrypted
    assert "effort" not in result["reasoning"]
    assert result["reasoning"]["summary"] == "concise"
    assert "reasoning.encrypted_content" in result["include"]


def test_build_request_virtual_model_maps_effort():
    body = {"messages": [{"role": "user", "content": "think hard"}]}
    result, meta = transform.build_grok_cli_request(
        "grok-4.5-high", body, {},
    )
    assert result["model"] == "grok-4.5"
    assert result["reasoning"]["effort"] == "high"
    assert meta["model"] == "grok-4.5"

    body = {"messages": [{"role": "user", "content": "hi"}]}
    result, _ = transform.build_grok_cli_request("grok-4.5-low", body, {})
    assert result["reasoning"]["effort"] == "low"


def test_build_request_explicit_reasoning_effort_wins():
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "reasoning_effort": "max",
    }
    result, _ = transform.build_grok_cli_request("grok-4.5", body, {})
    assert result["reasoning"]["effort"] == "xhigh"
    assert "reasoning_effort" not in result


def test_build_request_normalizes_tools():
    body = {
        "messages": [{"role": "user", "content": "search it"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the web",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {"type": "web_search"},
        ],
        "tool_choice": {"type": "function", "function": {"name": "search"}},
    }
    result, _ = transform.build_grok_cli_request("grok-build", body, {})

    assert result["tools"][0] == {
        "type": "function",
        "name": "search",
        "description": "Search the web",
        "parameters": {"type": "object", "properties": {}},
    }
    assert result["tools"][1] == {"type": "web_search"}
    assert result["tool_choice"] == {"type": "function", "name": "search"}


def test_normalize_effort():
    assert transform.normalize_effort("max") == "xhigh"
    assert transform.normalize_effort("HIGH") == "high"
    assert transform.normalize_effort(None) == "high"
    assert transform.normalize_effort("bogus") == "high"


def test_count_user_turns():
    items = [
        {"type": "message", "role": "user", "content": "a"},
        {"type": "message", "role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"type": "function_call", "role": "user"},
    ]
    assert transform.count_user_turns(items) == 2
    assert transform.count_user_turns([]) == 1
    assert transform.count_user_turns("not a list") == 1


def test_supports_reasoning_effort():
    assert transform.supports_reasoning_effort("grok-4.5")
    assert transform.supports_reasoning_effort("grok-4.5-high")
    assert not transform.supports_reasoning_effort("grok-build")
    assert not transform.supports_reasoning_effort("")


# ── Response translation: Responses API -> Chat Completions ──────────────


def test_responses_to_openai_response_text():
    resp = {
        "id": "resp_abc",
        "created_at": 1700000000,
        "status": "completed",
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text": "Hello!"}],
        }],
        "usage": {
            "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
        },
    }
    result = transform.responses_to_openai_response(resp, "grok-build")

    assert result["object"] == "chat.completion"
    assert result["id"] == "chatcmpl-abc"
    choice = result["choices"][0]
    assert choice["message"]["content"] == "Hello!"
    assert choice["finish_reason"] == "stop"
    assert result["usage"]["prompt_tokens"] == 10
    assert result["usage"]["completion_tokens"] == 5


def test_responses_to_openai_response_tool_calls():
    resp = {
        "id": "resp_xyz",
        "status": "completed",
        "output": [{
            "type": "function_call",
            "call_id": "fc_1",
            "name": "search",
            "arguments": "{\"q\": \"test\"}",
        }],
    }
    result = transform.responses_to_openai_response(resp, "grok-build")
    choice = result["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["tool_calls"] == [{
        "id": "fc_1",
        "type": "function",
        "function": {"name": "search", "arguments": "{\"q\": \"test\"}"},
    }]


# ── Stream translation: Responses SSE -> Chat SSE ────────────────────────


def _sse_line(event: dict) -> str:
    return f"data: {json.dumps(event)}"


def test_stream_translator_text_flow():
    t = ResponsesUpstreamTranslator(model="grok-build")

    events = t.feed(_sse_line({
        "type": "response.created",
        "response": {"id": "resp_1"},
    }))
    assert len(events) == 1
    first = json.loads(events[0][6:])
    assert first["choices"][0]["delta"]["role"] == "assistant"

    events = t.feed(_sse_line({
        "type": "response.output_text.delta",
        "delta": "Hello",
    }))
    chunk = json.loads(events[0][6:])
    assert chunk["choices"][0]["delta"]["content"] == "Hello"

    events = t.feed(_sse_line({
        "type": "response.completed",
        "response": {
            "status": "completed",
            "usage": {"input_tokens": 3, "output_tokens": 2},
        },
    }))
    finish = json.loads(events[0][6:])
    assert finish["choices"][0]["finish_reason"] == "stop"
    usage_chunk = json.loads(events[1][6:])
    assert usage_chunk["usage"]["prompt_tokens"] == 3
    assert events[2] == "data: [DONE]\n\n"


def test_stream_translator_tool_call_flow():
    t = ResponsesUpstreamTranslator(model="grok-build")

    t.feed(_sse_line({"type": "response.created", "response": {}}))
    events = t.feed(_sse_line({
        "type": "response.output_item.added",
        "item": {
            "type": "function_call",
            "id": "fc_9",
            "call_id": "fc_9",
            "name": "get_time",
        },
    }))
    chunk = json.loads(events[0][6:])
    tc = chunk["choices"][0]["delta"]["tool_calls"][0]
    assert tc["id"] == "fc_9"
    assert tc["function"]["name"] == "get_time"

    events = t.feed(_sse_line({
        "type": "response.function_call_arguments.delta",
        "item_id": "fc_9",
        "delta": "{\"tz\": \"UTC\"}",
    }))
    chunk = json.loads(events[0][6:])
    delta_tc = chunk["choices"][0]["delta"]["tool_calls"][0]
    assert delta_tc["index"] == 0
    assert delta_tc["function"]["arguments"] == "{\"tz\": \"UTC\"}"

    events = t.feed(_sse_line({
        "type": "response.completed",
        "response": {"status": "completed"},
    }))
    finish = json.loads(events[0][6:])
    assert finish["choices"][0]["finish_reason"] == "tool_calls"


def test_stream_translator_ignores_noise_and_malformed():
    t = ResponsesUpstreamTranslator(model="grok-build")
    assert t.feed("event: response.created") == []
    assert t.feed(": keep-alive") == []
    assert t.feed("data: {not json") == []
    assert t.feed("data: [DONE]") == []


def test_stream_translator_close_without_completed_emits_done():
    """Upstream closed mid-stream → still emit finish_reason + [DONE]."""
    t = ResponsesUpstreamTranslator(model="grok-build")
    t.feed(_sse_line({
        "type": "response.created",
        "response": {"id": "resp_1"},
    }))
    t.feed(_sse_line({
        "type": "response.output_text.delta",
        "delta": "Hi",
    }))
    events = t.close()
    assert events, "close() must emit terminal chat SSE"
    finish = json.loads(events[0][6:])
    assert finish["choices"][0]["finish_reason"] in (
        "stop", "length",
    )
    assert events[-1] == "data: [DONE]\n\n"
    assert t.close() == []


def test_stream_translator_close_noop_after_completed():
    t = ResponsesUpstreamTranslator(model="grok-build")
    t.feed(_sse_line({"type": "response.created", "response": {}}))
    t.feed(_sse_line({
        "type": "response.completed",
        "response": {"status": "completed"},
    }))
    assert t.close() == []
