"""Sanitize chat bodies before they hit Mistral's API.

Hermes/Kimi/Pi/etc. send client-only or OpenAI-only fields that
Mistral rejects with 422 extra_forbidden (e.g. store, max_context).

Reasoning knobs follow upstream ``capabilities.reasoning`` (cached
from GET /models): True → clamp effort to none|high; False → drop;
None (not fetched yet) → keep + clamp, 422 strip-retry handles miss.
"""

from __future__ import annotations

import json

_DROP_ALWAYS = (
    "max_context_size",
    "max_context",
    "context_length",
    # OpenAI Chat Completions extras — Pi Agent sends store=false
    "store",
)

_DROP_UNLESS_REASONING = (
    "reasoning",
    "reasoning_effort",
    "thinking",
    "think",
)

# Mistral accepts only these for reasoning effort (error 3051).
_EFFORT_NONE = frozenset({
    "none", "off", "false", "0", "minimal", "disable", "disabled",
})
_EFFORT_HIGH = frozenset({
    "high", "xhigh", "max", "maximum", "ultra",
})


def supports_reasoning(model: str) -> bool | None:
    """Upstream capabilities.reasoning, or None if cache miss."""
    from app.providers.mistral.models import reasoning_capability

    return reasoning_capability(model)


def body_has_reasoning_fields(body: dict) -> bool:
    """True if *body* (or extra_body) carries reasoning knobs."""
    if not isinstance(body, dict):
        return False
    for key in _DROP_UNLESS_REASONING:
        if key in body:
            return True
    extra = body.get("extra_body")
    if isinstance(extra, dict):
        for key in _DROP_UNLESS_REASONING:
            if key in extra:
                return True
    return False


def strip_reasoning_fields(body: dict) -> dict:
    """Copy *body* without reasoning knobs (same-conn 422 retry)."""
    out = dict(body)
    for key in _DROP_UNLESS_REASONING:
        out.pop(key, None)
    extra = out.get("extra_body")
    if isinstance(extra, dict):
        extra = dict(extra)
        for key in _DROP_UNLESS_REASONING:
            extra.pop(key, None)
        if extra:
            out["extra_body"] = extra
        else:
            out.pop("extra_body", None)
    return out


def normalize_reasoning_effort(value: object) -> str | None:
    """Map client effort strings to Mistral none|high, or None to drop."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "high" if value else "none"
    text = str(value).strip().lower()
    if not text:
        return None
    if text in _EFFORT_NONE:
        return "none"
    if text in _EFFORT_HIGH:
        return "high"
    # medium / low / unknown from Pi → high (reasoning on)
    return "high"


def _clamp_reasoning_fields(out: dict) -> None:
    """Rewrite reasoning_effort (+ nested reasoning.effort) in place."""
    if "reasoning_effort" in out:
        mapped = normalize_reasoning_effort(out.get("reasoning_effort"))
        if mapped is None:
            out.pop("reasoning_effort", None)
        else:
            out["reasoning_effort"] = mapped
    reasoning = out.get("reasoning")
    if isinstance(reasoning, dict):
        nested = dict(reasoning)
        if "effort" in nested:
            mapped = normalize_reasoning_effort(nested.get("effort"))
            if mapped is None:
                nested.pop("effort", None)
            else:
                nested["effort"] = mapped
        if nested:
            out["reasoning"] = nested
        else:
            out.pop("reasoning", None)


def _apply_reasoning_policy(
    target: dict, reasoning: bool | None,
) -> None:
    """Drop, clamp, or keep+clamp reasoning keys on *target*."""
    if reasoning is False:
        for key in _DROP_UNLESS_REASONING:
            target.pop(key, None)
        return
    if reasoning is True:
        _clamp_reasoning_fields(target)
        return
    # Unknown: keep fields but clamp effort if present.
    if body_has_reasoning_fields(target):
        _clamp_reasoning_fields(target)


def sanitize_mistral_chat_body(
    model: str,
    body: dict,
    *,
    reasoning: bool | None = None,
) -> dict:
    """Copy *body*, set upstream model, drop unsupported extras."""
    if reasoning is None:
        reasoning = supports_reasoning(model)
    out = dict(body)
    out["model"] = model
    for key in _DROP_ALWAYS:
        out.pop(key, None)
    extra = out.get("extra_body")
    if isinstance(extra, dict):
        extra = dict(extra)
        for key in _DROP_ALWAYS:
            extra.pop(key, None)
        _apply_reasoning_policy(extra, reasoning)
        if extra:
            out["extra_body"] = extra
        else:
            out.pop("extra_body", None)
    _apply_reasoning_policy(out, reasoning)
    messages = out.get("messages")
    if isinstance(messages, list):
        out["messages"] = [
            {**m, "role": "system"}
            if isinstance(m, dict) and m.get("role") == "developer"
            else m
            for m in messages
        ]
    return out


def _thinking_text(part: dict) -> str:
    """Flatten Mistral thinking block to plain text."""
    thinking = part.get("thinking")
    if isinstance(thinking, str):
        return thinking
    if not isinstance(thinking, list):
        return ""
    bits: list[str] = []
    for item in thinking:
        if isinstance(item, dict) and item.get("text"):
            bits.append(str(item["text"]))
        elif isinstance(item, str):
            bits.append(item)
    return "".join(bits)


def flatten_mistral_content(
    content: object,
    *,
    keep_thinking_fallback: bool = True,
) -> str | None:
    """Flatten Magistral list content to an OpenAI string.

    Magistral returns::

        [{"type":"thinking",...}, {"type":"text","text":"..."}]

    Clients that stringify parts get ``[object Object]``. We keep only
    ``type:text`` (and bare text). Thinking is dropped so agents do not
    treat the plan as the answer. If there is no text part and
    *keep_thinking_fallback* is True, thinking is promoted to content
    so a thinking-only payload is not erased.
    """
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    texts: list[str] = []
    reasons: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            texts.append(str(part))
            continue
        ptype = part.get("type")
        if ptype == "thinking":
            bit = _thinking_text(part)
            if bit:
                reasons.append(bit)
        elif ptype == "text" or "text" in part:
            texts.append(str(part.get("text") or ""))
    if texts:
        return "".join(texts)
    if keep_thinking_fallback and reasons:
        return "".join(reasons)
    return ""


def _apply_flat_content(
    target: dict,
    content: object,
    *,
    keep_thinking_fallback: bool,
) -> None:
    """Rewrite list-shaped content to a string in place. No other fields."""
    if not isinstance(content, list):
        return
    target["content"] = flatten_mistral_content(
        content,
        keep_thinking_fallback=keep_thinking_fallback,
    )


def normalize_mistral_completion(data: dict) -> dict:
    """Flatten Magistral list content in a chat.completion body."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    choices = out.get("choices")
    if not isinstance(choices, list):
        return out
    new_choices: list = []
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        ch = dict(choice)
        msg = ch.get("message")
        if isinstance(msg, dict):
            msg = dict(msg)
            # Final message: keep thinking only if there is no text.
            _apply_flat_content(
                msg, msg.get("content"),
                keep_thinking_fallback=True,
            )
            ch["message"] = msg
        delta = ch.get("delta")
        if isinstance(delta, dict):
            delta = dict(delta)
            # Stream deltas: never promote thinking (would flood the
            # client with the plan). Empty thinking-only → "".
            _apply_flat_content(
                delta, delta.get("content"),
                keep_thinking_fallback=False,
            )
            ch["delta"] = delta
        new_choices.append(ch)
    out["choices"] = new_choices
    return out


def normalize_mistral_sse_line(line: str) -> str | None:
    """Rewrite one SSE line if content is a Magistral part list.

    Returns None to drop thinking-only deltas (empty content, no
    role/tool_calls/finish_reason) so agents do not see the plan as
    the answer. String content lines are never modified.
    """
    stripped = line.strip()
    if not stripped.startswith("data:"):
        return line
    payload = stripped[5:].strip()
    if not payload or payload == "[DONE]":
        return line
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return line
    if not isinstance(data, dict):
        return line
    needs = False
    for choice in data.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        for key in ("delta", "message"):
            block = choice.get(key)
            if isinstance(block, dict) and isinstance(
                block.get("content"), list,
            ):
                needs = True
                break
        if needs:
            break
    if not needs:
        return line
    fixed = normalize_mistral_completion(data)
    # Drop pure thinking deltas: empty content and nothing else useful.
    for choice in fixed.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            continue
        useful = any(
            delta.get(k)
            for k in ("role", "tool_calls", "function_call")
        )
        if choice.get("finish_reason"):
            useful = True
        content = delta.get("content")
        if (
            not useful
            and (content is None or content == "")
            and "content" in delta
        ):
            return None
    return f"data: {json.dumps(fixed, ensure_ascii=False)}"
