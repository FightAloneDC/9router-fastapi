"""Test-model completion parse: JSON bodies vs Qoder-style SSE."""

import json

from app.routers.models import parse_test_completion


def test_plain_json_choices_are_ok() -> None:
    """Mistral (and other OpenAI-compat) return JSON, not SSE."""
    body = {
        "id": "cmpl",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "hi"},
        }],
    }
    ok, err = parse_test_completion(json.dumps(body))
    assert ok is True
    assert err is None


def test_plain_json_is_not_treated_as_empty_sse() -> None:
    raw = json.dumps({"choices": [{"message": {"content": "x"}}]})
    assert not raw.startswith("data:")
    ok, err = parse_test_completion(raw)
    assert ok is True
    assert err is None


def test_empty_body_is_timeout_or_empty() -> None:
    ok, err = parse_test_completion("")
    assert ok is False
    assert err is not None
    assert "no completion choices" in err


def test_json_error_object_is_surfaced() -> None:
    body = {"error": {"message": "Rate limit exceeded"}}
    ok, err = parse_test_completion(json.dumps(body))
    assert ok is False
    assert err == "Rate limit exceeded"


def test_sse_data_line_choices_are_ok() -> None:
    raw = (
        'data: {"choices":[{"delta":{"content":"x"}}]}\n'
        "data: [DONE]\n"
    )
    ok, err = parse_test_completion(raw)
    assert ok is True
    assert err is None


class _UnwrapHandler:
    def unwrap_response(self, text: str) -> dict:
        del text
        return {"choices": [{"message": {"content": "ok"}}]}


def test_handler_unwrap_recovers_non_json_envelope() -> None:
    ok, err = parse_test_completion(
        "not-json",
        handler=_UnwrapHandler(),
    )
    assert ok is True
    assert err is None
