"""Mistral request sanitizer: capability-driven reasoning + flatten."""

import json

from app.providers.mistral.models import (
    clear_reasoning_cache,
    parse_response,
    remember_reasoning,
)
from app.providers.mistral.transform import (
    flatten_mistral_content,
    normalize_mistral_completion,
    normalize_mistral_sse_line,
    sanitize_mistral_chat_body,
    supports_reasoning,
)


def setup_function() -> None:
    clear_reasoning_cache()


def test_parse_response_caches_reasoning_capability() -> None:
    rows = parse_response({
        "data": [
            {
                "id": "magistral-small-latest",
                "capabilities": {"completion_chat": True, "reasoning": True},
            },
            {
                "id": "codestral-latest",
                "capabilities": {
                    "completion_chat": True,
                    "reasoning": False,
                },
            },
            {"id": "mistral-embed", "capabilities": {}},
        ],
    })
    assert len(rows) == 3
    assert supports_reasoning("magistral-small-latest") is True
    assert supports_reasoning("codestral-latest") is False
    assert supports_reasoning("mistral-embed") is False
    assert supports_reasoning("unknown-model") is None


def test_cache_miss_is_none() -> None:
    assert supports_reasoning("magistral-medium-latest") is None


def test_drops_max_context_size_and_reasoning() -> None:
    remember_reasoning("codestral-latest", False)
    body = {
        "model": "mi/codestral-latest",
        "messages": [{"role": "user", "content": "hi"}],
        "max_context_size": 256000,
        "store": False,
        "reasoning": {"effort": "xhigh"},
        "reasoning_effort": "xhigh",
        "thinking": True,
        "think": False,
        "extra_body": {
            "max_context_size": 128000,
            "store": False,
            "reasoning_effort": "high",
        },
    }
    out = sanitize_mistral_chat_body("codestral-latest", body)
    assert out["model"] == "codestral-latest"
    assert "max_context_size" not in out
    assert "store" not in out
    assert "reasoning" not in out
    assert "reasoning_effort" not in out
    assert "thinking" not in out
    assert "think" not in out
    assert "extra_body" not in out


def test_unknown_capability_keeps_and_clamps_reasoning() -> None:
    out = sanitize_mistral_chat_body(
        "codestral-latest",
        {
            "messages": [{"role": "user", "content": "hi"}],
            "reasoning_effort": "medium",
        },
    )
    assert out["reasoning_effort"] == "high"


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
    remember_reasoning("magistral-medium-latest", True)
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


def test_magistral_clamps_medium_effort_to_high() -> None:
    remember_reasoning("magistral-small-latest", True)
    out = sanitize_mistral_chat_body(
        "magistral-small-latest",
        {
            "model": "mi/magistral-small-latest",
            "messages": [{"role": "user", "content": "hi"}],
            "reasoning_effort": "medium",
            "reasoning": {"effort": "medium"},
            "extra_body": {"reasoning_effort": "low"},
        },
    )
    assert out["reasoning_effort"] == "high"
    assert out["reasoning"]["effort"] == "high"
    assert out["extra_body"]["reasoning_effort"] == "high"


def test_magistral_maps_none_effort() -> None:
    remember_reasoning("magistral-small-latest", True)
    out = sanitize_mistral_chat_body(
        "magistral-small-latest",
        {
            "messages": [{"role": "user", "content": "hi"}],
            "reasoning_effort": "none",
        },
    )
    assert out["reasoning_effort"] == "none"


def test_flatten_magistral_thinking_and_text() -> None:
    text = flatten_mistral_content([
        {
            "type": "thinking",
            "thinking": [{"type": "text", "text": "plan "}],
            "closed": True,
        },
        {
            "type": "thinking",
            "thinking": [{"type": "text", "text": "more"}],
            "closed": True,
        },
        {"type": "text", "text": "- Tanggal: 17"},
    ])
    assert text == "- Tanggal: 17"


def test_flatten_drops_thinking_without_fallback() -> None:
    assert flatten_mistral_content(
        [{
            "type": "thinking",
            "thinking": [{"type": "text", "text": "plan"}],
        }],
        keep_thinking_fallback=False,
    ) == ""


def test_flatten_thinking_only_fallback() -> None:
    assert flatten_mistral_content(
        [{
            "type": "thinking",
            "thinking": [{"type": "text", "text": "only"}],
        }],
        keep_thinking_fallback=True,
    ) == "only"


def test_normalize_completion_flattens_message_content() -> None:
    raw = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": [
                            {"type": "text", "text": "why"},
                        ],
                    },
                    {"type": "text", "text": "pong"},
                ],
            },
        }],
    }
    out = normalize_mistral_completion(raw)
    msg = out["choices"][0]["message"]
    assert msg["content"] == "pong"
    assert "reasoning_content" not in msg


def test_normalize_sse_line_drops_thinking_delta() -> None:
    line = (
        'data: {"choices":[{"delta":{"content":'
        '[{"type":"thinking","thinking":'
        '[{"type":"text","text":"Hi"}]}]},'
        '"finish_reason":null}]}'
    )
    assert normalize_mistral_sse_line(line) is None


def test_normalize_sse_line_keeps_text_part() -> None:
    line = (
        'data: {"choices":[{"delta":{"content":'
        '[{"type":"text","text":"pong"}]},'
        '"finish_reason":null}]}'
    )
    out = normalize_mistral_sse_line(line)
    assert out is not None
    payload = json.loads(out[6:])
    assert payload["choices"][0]["delta"]["content"] == "pong"


def test_normalize_sse_line_passes_string_content() -> None:
    line = (
        'data: {"choices":[{"delta":{"content":"ong"},'
        '"finish_reason":null}]}'
    )
    assert normalize_mistral_sse_line(line) == line


def test_handler_unwrap_flattens_content() -> None:
    from app.providers.mistral.config import MistralConfig
    from app.providers.mistral.handler import MistralHandler

    handler = MistralHandler(MistralConfig())
    data = handler.unwrap_response(json.dumps({
        "choices": [{
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "ok"},
                ],
            },
        }],
    }))
    assert data["choices"][0]["message"]["content"] == "ok"


def test_handler_build_request_encodes_sanitized_json() -> None:
    import asyncio

    from app.providers.mistral.config import MistralConfig
    from app.providers.mistral.handler import MistralHandler

    remember_reasoning("codestral-latest", False)
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


def test_mistral_rewrite_strips_reasoning_on_422() -> None:
    from app.providers.mistral.handler import (
        mistral_rewrite_body_after_error,
    )

    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "reasoning_effort": "high",
    }
    # Cache miss → strip on 422
    out = mistral_rewrite_body_after_error(
        422, "extra_forbidden", "codestral-latest", body,
    )
    assert out is not None
    assert "reasoning_effort" not in out

    remember_reasoning("magistral-small-latest", True)
    assert mistral_rewrite_body_after_error(
        422, "extra_forbidden", "magistral-small-latest", body,
    ) is None

    remember_reasoning("codestral-latest", False)
    out2 = mistral_rewrite_body_after_error(
        422, "extra_forbidden", "codestral-latest", body,
    )
    assert out2 is not None
    assert "reasoning_effort" not in out2


def test_mistral_rewrite_strips_on_400_code_3051() -> None:
    from app.providers.mistral.handler import (
        mistral_rewrite_body_after_error,
    )

    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "reasoning_effort": "high",
        "reasoning": {"effort": "high"},
    }
    err = (
        '{"object":"error","message":"Reasoning Effort is not '
        'enabled for this model","type":"invalid_request_error",'
        '"code":3051}'
    )
    # Even if cache wrongly says True, upstream 3051 wins.
    remember_reasoning("codestral-latest", True)
    out = mistral_rewrite_body_after_error(
        400, err, "codestral-latest", body,
    )
    assert out is not None
    assert "reasoning_effort" not in out
    assert "reasoning" not in out
    # Learned: next sanitize drops without waiting for 400 again.
    assert supports_reasoning("codestral-latest") is False

    # Unrelated 400 must not strip.
    assert mistral_rewrite_body_after_error(
        400, "invalid_model", "codestral-latest", body,
    ) is None


def test_mistral_no_fallback_labs_not_enabled() -> None:
    from app.providers.mistral.handler import mistral_should_fallback

    err = (
        '{"object":"error","message":"Model labs-leanstral-1-5 is a '
        'Labs model. To use Labs models, an admin must enable them",'
        '"type":"labs_not_enabled"}'
    )
    assert mistral_should_fallback(403, err) is False
    assert mistral_should_fallback(422, '{"type":"extra_forbidden"}') is False
    assert mistral_should_fallback(429, "Rate limit exceeded") is False
    assert mistral_should_fallback(
        400, '{"type":"rate_limited"}',
    ) is False


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


def test_alims_rerank_url_default_not_doubled() -> None:
    from app.providers.alims_intl.config import AlimsIntlConfig
    from app.providers.alims_intl.handler import rerank_url

    # Public DashScope chat BASE_URL maps to compatible-api for
    # rerank (compatible-mode/v1/reranks 404s on this host).
    url = rerank_url(AlimsIntlConfig().BASE_URL)
    assert url.count("/compatible-api/v1") == 1
    assert "/compatible-mode/" not in url
    assert url == (
        "https://dashscope-intl.aliyuncs.com"
        "/compatible-api/v1/reranks"
    )


def test_alims_rerank_url_shapes() -> None:
    from app.providers.alims_intl.handler import rerank_url

    assert rerank_url(
        "https://ws.ap-southeast-1.maas.aliyuncs.com"
        "/compatible-mode/v1"
    ) == (
        "https://ws.ap-southeast-1.maas.aliyuncs.com"
        "/compatible-mode/v1/reranks"
    )
    assert rerank_url("https://host.example") == (
        "https://host.example/compatible-mode/v1/reranks"
    )
    assert rerank_url(
        "https://dashscope-intl.aliyuncs.com"
        "/compatible-mode/v1/"
    ) == (
        "https://dashscope-intl.aliyuncs.com"
        "/compatible-api/v1/reranks"
    )
    assert rerank_url(
        "https://dashscope-intl.aliyuncs.com"
        "/compatible-api/v1"
    ) == (
        "https://dashscope-intl.aliyuncs.com"
        "/compatible-api/v1/reranks"
    )
    assert rerank_url("") == "/compatible-mode/v1/reranks"
