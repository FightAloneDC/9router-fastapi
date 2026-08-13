"""Sanitize chat bodies before they hit Mistral's API.

Hermes/Kimi/etc. send client-only fields (max_context_size) and
reasoning knobs that codestral and most Mistral chat models reject.
"""

from __future__ import annotations

_DROP_ALWAYS = (
    "max_context_size",
    "max_context",
    "context_length",
)

_DROP_UNLESS_REASONING = (
    "reasoning",
    "reasoning_effort",
    "thinking",
    "think",
)

_REASONING_MODELS = ("magistral",)


def supports_reasoning(model: str) -> bool:
    """True for Mistral models that accept reasoning knobs."""
    mid = (model or "").lower()
    return any(tag in mid for tag in _REASONING_MODELS)


def sanitize_mistral_chat_body(
    model: str, body: dict,
) -> dict:
    """Copy *body*, set upstream model, drop unsupported extras."""
    out = dict(body)
    out["model"] = model
    for key in _DROP_ALWAYS:
        out.pop(key, None)
    extra = out.get("extra_body")
    if isinstance(extra, dict):
        extra = dict(extra)
        for key in _DROP_ALWAYS:
            extra.pop(key, None)
        if not supports_reasoning(model):
            for key in _DROP_UNLESS_REASONING:
                extra.pop(key, None)
        if extra:
            out["extra_body"] = extra
        else:
            out.pop("extra_body", None)
    if not supports_reasoning(model):
        for key in _DROP_UNLESS_REASONING:
            out.pop(key, None)
    messages = out.get("messages")
    if isinstance(messages, list):
        out["messages"] = [
            {**m, "role": "system"}
            if isinstance(m, dict) and m.get("role") == "developer"
            else m
            for m in messages
        ]
    return out
