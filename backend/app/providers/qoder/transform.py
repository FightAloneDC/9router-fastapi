"""Qoder request/response transformation.

Transforms OpenAI-format requests to Qoder format and unwraps Qoder responses.
"""

import hashlib
import json
import uuid
from typing import Any


def _stable_hash(prefix: str, *parts: str) -> str:
    """Generate a stable hash from prefix and parts."""
    h = hashlib.sha256()
    h.update(prefix.encode())
    for p in parts:
        h.update(b"\0")
        h.update(str(p or "").encode())
    return h.hexdigest()[:16]


def _stable_chat_record_id(model: str, messages: list, tools: list | None, max_tokens: int) -> str:
    """Generate a stable chat record ID."""
    h = hashlib.sha256()
    h.update(b"qoder-record\0")
    h.update(model.encode())
    for m in messages:
        if not m or not isinstance(m, dict):
            continue
        if m.get("role"):
            h.update(b"\0")
            h.update(m["role"].encode())
        content = m.get("content", "")
        if isinstance(content, str) and content:
            h.update(b"\0")
            h.update(content.encode())
    if tools:
        h.update(b"\0")
        try:
            h.update(json.dumps(tools).encode())
        except Exception:
            pass
    h.update(f"\0mt={max_tokens}".encode())
    return h.hexdigest()[:16]


def _normalize_messages(messages: list[dict]) -> tuple[list[dict], str]:
    """Normalize messages and extract system text.

    Returns:
        (messages_without_system, system_text)
    """
    if not messages:
        return [], ""

    system_parts = []
    out = []

    for msg in messages:
        if not msg or not isinstance(msg, dict):
            continue

        content = msg.get("content", "")
        if isinstance(content, list):
            # Handle multipart content
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            content = "\n".join(text_parts)

        if msg.get("role") == "system":
            if content:
                system_parts.append(content)
            continue

        cloned = dict(msg)
        cloned["content"] = content
        out.append(cloned)

    return out, "\n\n".join(system_parts)


def _last_user_text(messages: list[dict]) -> str:
    """Get the last user message text."""
    for m in reversed(messages):
        if m and m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return ""


def _truncate(s: str, n: int) -> str:
    """Truncate string to n characters."""
    if s and len(s) > n:
        return s[:n] + "..."
    return s or ""


def build_qoder_request_body(
    model: str,
    body: dict[str, Any],
    credentials: dict[str, Any],
    model_config: dict[str, Any] | None = None,
    qoder_key: str = "",
) -> dict[str, Any]:
    """Transform OpenAI-format request to Qoder format.

    Args:
        model: Catalog remainder / public id (e.g., "auto" or "qd/auto")
        body: OpenAI-format request body
        credentials: Connection credentials
        model_config: Model config from catalog (optional, will use defaults if not provided)
        qoder_key: Upstream key (e.g., "auto"). If empty, uses model as-is.

    Returns:
        Qoder-format request body
    """
    if not qoder_key:
        qoder_key = model

    # Use provided model_config or create a minimal one
    if not model_config:
        model_config = {"key": qoder_key}

    # Normalize messages
    messages, system_text = _normalize_messages(body.get("messages", []))
    tools = body.get("tools")

    # Determine max tokens
    max_output_tokens = model_config.get("max_output_tokens", 0) or 0
    max_tokens = 32768
    if max_output_tokens > 0:
        max_tokens = max_output_tokens
    if isinstance(body.get("max_tokens"), (int, float)) and 0 < body["max_tokens"] < max_tokens:
        max_tokens = int(body["max_tokens"])
    if isinstance(body.get("max_completion_tokens"), (int, float)) and 0 < body["max_completion_tokens"] < max_tokens:
        max_tokens = int(body["max_completion_tokens"])

    # Get user info
    psd = credentials.get("provider_specific", {})
    user_id = psd.get("userId", "")

    # Generate IDs
    last_user = _last_user_text(messages)
    session_id = _stable_hash("qoder-session", user_id, qoder_key)
    record_id = _stable_chat_record_id(qoder_key, messages, tools, max_tokens)
    is_reasoning = model_config.get("is_reasoning", False)

    return {
        "request_id": str(uuid.uuid4()),
        "request_set_id": record_id,
        "chat_record_id": record_id,
        "session_id": session_id,
        "stream": True,
        "chat_task": "FREE_INPUT",
        "is_reply": True,
        "is_retry": False,
        "source": 1,
        "version": "3",
        "session_type": "qodercli",
        "agent_id": "agent_common",
        "task_id": "common",
        "code_language": "",
        "chat_prompt": "",
        "image_urls": None,
        "aliyun_user_type": "",
        "system": system_text,
        "messages": messages,
        "tools": tools if isinstance(tools, list) else [],
        "parameters": {"max_tokens": max_tokens},
        "chat_context": {
            "chatPrompt": "",
            "imageUrls": None,
            "extra": {
                "context": [],
                "modelConfig": {"key": qoder_key, "is_reasoning": is_reasoning},
                "originalContent": last_user,
            },
            "features": [],
            "text": last_user,
        },
        "model_config": model_config,
        "business": {
            "product": "cli",
            "version": "1.0.0",
            "type": "agent",
            "stage": "start",
            "id": str(uuid.uuid4()),
            "name": _truncate(last_user, 30),
            "begin_at": int(__import__("time").time() * 1000),
        },
    }


def qoder_envelope_http_error(
    envelope: dict,
) -> tuple[int, str] | None:
    """Map Qoder business-error JSON to (http_status, detail).

    Upstream may send a bare envelope then drop the connection:
      {"code":"112","message":"{\\"pricingUrl\\":\\"https://...\\"}"}
    Hermes then surfaces IncompleteRead / empty Proxy error after a long
    wait. Detecting this early enables cooldown + connection fallback.
    """
    if not isinstance(envelope, dict):
        return None
    if "choices" in envelope or "statusCodeValue" in envelope:
        return None
    if "headers" in envelope and "body" in envelope:
        return None
    if envelope.get("code") is None:
        return None

    code_s = str(envelope.get("code"))
    msg = envelope.get("message", "")
    msg_s = msg if isinstance(msg, str) else json.dumps(msg)
    lower = msg_s.lower()

    if (
        code_s == "112"
        or "pricingurl" in lower
        or "pricing" in lower
    ):
        return (
            402,
            f"Qoder quota/pricing code={code_s}: {msg_s[:300]}",
        )
    if (
        code_s in ("105", "TOKEN_EXPIRE")
        or "login expired" in lower
        or "token is not active" in lower
    ):
        return (
            403,
            f"Qoder auth code={code_s}: {msg_s[:300]}",
        )
    return 502, f"Qoder error code={code_s}: {msg_s[:300]}"


def _qoder_error_sse_chunk(status: int, detail: str) -> str:
    """Build OpenAI-style SSE chunk embedding a [qoder error ...] marker."""
    now = int(__import__("time").time())
    error_chunk = json.dumps({
        "id": f"qoder-error-{now}",
        "object": "chat.completion.chunk",
        "created": now,
        "model": "qoder",
        "choices": [{
            "index": 0,
            "delta": {
                "content": (
                    f"\n[qoder error {status}: "
                    f"{_truncate(detail, 200)}]"
                ),
            },
            "finish_reason": "stop",
        }],
    })
    return f"data: {error_chunk}"


def unwrap_qoder_sse_line(line: str) -> str | None:
    """Unwrap a single Qoder SSE line to OpenAI format.

    Qoder may send:
      - New: data: {"headers":{...},"body":"..."}
      - Old: data: {"statusCodeValue":200,"body":"..."}
      - Business error: data: {"code":"112","message":"..."}
      - Direct: data: {"choices":[...],...}

    Returns:
        Unwrapped line or None if should be skipped
    """
    trimmed = line.strip()
    if not trimmed or not trimmed.startswith("data:"):
        return None

    data = trimmed[5:].strip()
    if data == "[DONE]":
        return "data: [DONE]"

    try:
        envelope = json.loads(data)
    except json.JSONDecodeError:
        return None

    if not isinstance(envelope, dict):
        return None

    # Business error envelope (quota/auth) — before body formats
    biz = qoder_envelope_http_error(envelope)
    if biz is not None:
        status, detail = biz
        return _qoder_error_sse_chunk(status, detail)

    # Direct OpenAI chunk (no envelope wrapper)
    if "choices" in envelope or (
        "error" in envelope and "body" not in envelope
    ):
        sanitized = data.replace("\r\n", "").replace("\n", "")
        return f"data: {sanitized}"

    def _from_inner(inner: str) -> str | None:
        if not inner:
            return None
        if inner == "[DONE]":
            return "data: [DONE]"
        # Inner may itself be a business-error JSON object
        try:
            inner_obj = json.loads(inner)
        except json.JSONDecodeError:
            inner_obj = None
        if isinstance(inner_obj, dict):
            inner_biz = qoder_envelope_http_error(inner_obj)
            if inner_biz is not None:
                st, detail = inner_biz
                return _qoder_error_sse_chunk(st, detail)
        sanitized = inner.replace("\r\n", "").replace("\n", "")
        return f"data: {sanitized}"

    # New format: {"headers":{...},"body":"..."}
    if "headers" in envelope and "body" in envelope:
        return _from_inner(envelope.get("body", "") or "")

    # Old format: {"statusCodeValue":200,"body":"..."}
    status = envelope.get("statusCodeValue", 200)
    inner = envelope.get("body", "")

    if status != 200:
        return _qoder_error_sse_chunk(
            int(status) if str(status).isdigit() else 502,
            str(inner),
        )

    return _from_inner(inner if isinstance(inner, str) else "")


def unwrap_qoder_response(response_text: str) -> dict[str, Any]:
    """Unwrap a non-streaming Qoder response to OpenAI format.

    Qoder may return:
      1. SSE format:  data:{"headers":{...},"body":"..."}  data:[DONE]
      2. Envelope:    {"statusCodeValue":200,"body":"..."}
      3. Direct JSON: {"choices":[...],"usage":{...}}

    Args:
        response_text: Raw response text from Qoder

    Returns:
        OpenAI-format response dict
    """
    # Handle SSE format (data: prefix) — Qoder always returns SSE even for
    # non-streaming requests.  We collect all chunks and build a single
    # OpenAI-format response with aggregated content.
    text = response_text.strip()
    if text.startswith("data:"):
        chunks = []
        for line in text.split("\n"):
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
                # New format: {"headers":{...},"body":"..."}
                if "body" in obj and isinstance(obj["body"], str):
                    try:
                        inner = json.loads(obj["body"])
                        if isinstance(inner, dict) and "choices" in inner:
                            chunks.append(inner)
                            continue
                    except json.JSONDecodeError:
                        pass
                # Old format: {"statusCodeValue":200,"body":"..."}
                status = obj.get("statusCodeValue", 200)
                if status == 200 and "body" in obj:
                    try:
                        inner = json.loads(obj["body"])
                        if isinstance(inner, dict):
                            chunks.append(inner)
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass
                # Direct OpenAI chunk
                if "choices" in obj:
                    chunks.append(obj)
            except json.JSONDecodeError:
                continue

        if not chunks:
            return {
                "error": {
                    "message": f"Failed to parse Qoder SSE response: {response_text[:200]}",
                    "type": "qoder_error",
                }
            }

        # Aggregate streaming chunks into a single response
        content = ""
        reasoning_content = ""
        usage = {}
        model = ""
        chat_id = ""
        created = 0
        for chunk in chunks:
            model = chunk.get("model", model)
            chat_id = chunk.get("id", chat_id)
            created = chunk.get("created", created)
            if "usage" in chunk and chunk["usage"]:
                usage = chunk["usage"]
            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})
                content += delta.get("content", "")
                reasoning_content += delta.get("reasoning_content", "")

        result: dict[str, Any] = {
            "id": chat_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }],
        }
        if reasoning_content:
            result["choices"][0]["message"]["reasoning_content"] = reasoning_content
        if usage:
            result["usage"] = usage
        return result

    # Plain JSON envelope
    try:
        envelope = json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "error": {
                "message": f"Failed to parse Qoder response: {response_text[:200]}",
                "type": "qoder_error",
            }
        }

    biz = qoder_envelope_http_error(envelope)
    if biz is not None:
        status, detail = biz
        return {
            "error": {
                "message": detail,
                "type": "qoder_error",
                "code": status,
            }
        }

    # Direct OpenAI format
    if "choices" in envelope:
        return envelope

    status = envelope.get("statusCodeValue", 200)
    inner = envelope.get("body", "")

    if status != 200:
        return {
            "error": {
                "message": f"Qoder error {status}: {inner}",
                "type": "qoder_error",
            }
        }

    if isinstance(inner, str):
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            return {
                "error": {
                    "message": f"Failed to parse Qoder inner response: {inner[:200]}",
                    "type": "qoder_error",
                }
            }

    return inner if isinstance(inner, dict) else {"error": {"message": "Unexpected Qoder response format"}}
