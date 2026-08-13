"""Mistral request sanitizer: drop context/reasoning extras."""

import json

from app.providers.mistral.transform import (
    sanitize_mistral_chat_body,
    supports_reasoning,
)


def test_codestral_does_not_support_reasoning() -> None:
    assert supports_reasoning("codestral-latest") is False
    assert supports_reasoning("mistral-small-latest") is False
    assert supports_reasoning("magistral-medium-latest") is True


def test_drops_max_context_size_and_reasoning() -> None:
    body = {
        "model": "mi/codestral-latest",
        "messages": [{"role": "user", "content": "hi"}],
        "max_context_size": 256000,
        "reasoning": {"effort": "xhigh"},
        "reasoning_effort": "xhigh",
        "thinking": True,
        "think": False,
        "extra_body": {
            "max_context_size": 128000,
            "reasoning_effort": "high",
        },
    }
    out = sanitize_mistral_chat_body("codestral-latest", body)
    assert out["model"] == "codestral-latest"
    assert "max_context_size" not in out
    assert "reasoning" not in out
    assert "reasoning_effort" not in out
    assert "thinking" not in out
    assert "think" not in out
    assert "extra_body" not in out


def test_maps_developer_role_to_system() -> None:
    out = sanitize_mistral_chat_body("codestral-latest", {
        "model": "mi/codestral-latest",
        "messages": [
            {"role": "developer", "content": "sys"},
            {"role": "user", "content": "hi"},
        ],
    })
    assert out["messages"][0]["role"] == "system"
    assert out["messages"][1]["role"] == "user"


def test_keeps_reasoning_on_magistral() -> None:
    body = {
        "model": "mi/magistral-medium-latest",
        "messages": [{"role": "user", "content": "hi"}],
        "reasoning_effort": "high",
        "max_context_size": 128000,
    }
    out = sanitize_mistral_chat_body(
        "magistral-medium-latest", body,
    )
    assert out["reasoning_effort"] == "high"
    assert "max_context_size" not in out


def test_handler_build_request_encodes_sanitized_json() -> None:
    import asyncio

    from app.providers.mistral.config import MistralConfig
    from app.providers.mistral.handler import MistralHandler

    handler = MistralHandler(MistralConfig())
    raw, headers = asyncio.run(handler.build_request_body(
        "codestral-latest",
        {
            "model": "mi/codestral-latest",
            "max_context_size": 256000,
            "reasoning_effort": "xhigh",
            "messages": [{"role": "user", "content": "hi"}],
        },
        {},
    ))
    assert headers is None
    payload = json.loads(raw.decode())
    assert payload["model"] == "codestral-latest"
    assert "max_context_size" not in payload
    assert "reasoning_effort" not in payload


def test_alims_drops_invalid_reasoning_effort() -> None:
    import asyncio

    from app.providers.alims_intl.config import AlimsIntlConfig
    from app.providers.alims_intl.handler import AlimsIntlHandler

    handler = AlimsIntlHandler(AlimsIntlConfig())
    _headers, body = asyncio.run(handler.prepare_request(
        {},
        {
            "model": "deepseek-v4-flash-0731",
            "think": False,
            "reasoning_effort": "none",
            "messages": [
                {"role": "developer", "content": "sys"},
                {"role": "user", "content": "hi"},
            ],
        },
    ))
    assert body["messages"][0]["role"] == "system"
    assert "think" not in body
    assert "reasoning_effort" not in body
