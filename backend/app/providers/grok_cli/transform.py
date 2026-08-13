"""Grok CLI request/response transformation.

Port of the GrokCliExecutor request shaping from the Next.js reference
(``open-sse/executors/grok-cli.js``): Chat Completions -> Responses API
requests, plus Responses API responses -> Chat Completions.
"""

from __future__ import annotations

import json
import re
import socket
import time
import uuid
from typing import Any

from app.providers.grok_cli.constants import (
    GROK_CLI_EFFORT_LEVELS,
    GROK_CLI_DEFAULT_EFFORT,
    GROK_CLI_FREEFORM_TOOL_PARAMETERS,
    GROK_CLI_NATIVE_ITEM_ID,
    GROK_CLI_SESSION_TTL_SECONDS,
    GROK_CLI_TURN_STORE_MAX,
    HOSTED_TOOL_TYPES,
    RESPONSES_API_ALLOWLIST,
    SERVER_ID_PATTERN,
)

_SERVER_ID_RE = re.compile(SERVER_ID_PATTERN)
_NATIVE_ITEM_ID_RE = re.compile(GROK_CLI_NATIVE_ITEM_ID, re.IGNORECASE)
_GROK_45_RE = re.compile(r"^grok-4\.5(?:$|-)")

# Chat Completions fields dropped before forwarding to /responses
_CHAT_LEFTOVERS = (
    "messages",
    "max_tokens",
    "max_completion_tokens",
    "n",
    "seed",
    "logprobs",
    "top_logprobs",
    "frequency_penalty",
    "presence_penalty",
    "logit_bias",
    "user",
    "stream_options",
    "prompt_cache_retention",
    "safety_identifier",
    "previous_response_id",  # store=false -> cannot resolve
)

# Per-session last turn index (multi-turn headers never go backwards)
_session_turn_store: dict[str, dict] = {}


# ── Small helpers ────────────────────────────────────────────────────────


def supports_reasoning_effort(model: str) -> bool:
    """Only grok-4.5* models accept reasoning.effort."""
    return bool(_GROK_45_RE.match(str(model or "")))


def normalize_effort(value: Any) -> str:
    """Normalize reasoning effort; unknown values fall back to high."""
    effort = value.strip().lower() if isinstance(value, str) else ""
    if effort == "max":
        return "xhigh"
    if effort in GROK_CLI_EFFORT_LEVELS:
        return effort
    return GROK_CLI_DEFAULT_EFFORT


def resolve_effort_from_model(model_id: Any) -> str | None:
    """Effort level from a model name suffix (e.g. ``grok-4.5-high``).

    Mirrors ``resolveEffortFromModel`` in the reference executor: any
    model ending in ``-<effort>`` implies that effort, no hardcoded map.
    """
    if not model_id or not isinstance(model_id, str):
        return None
    for level in GROK_CLI_EFFORT_LEVELS:
        if model_id.endswith(f"-{level}"):
            return level
    return None


def count_user_turns(input_items: Any) -> int:
    """Count user message items (1-based conversation turn)."""
    if not isinstance(input_items, list):
        return 1
    count = 0
    for item in input_items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type", "")
        if item.get("role") == "user" and item_type in ("", "message"):
            count += 1
    return max(1, count)


def resolve_turn_idx(session_id: str, input_items: Any) -> int:
    """Monotonic turn index per session (never decreases)."""
    from_input = count_user_turns(input_items)
    if not session_id:
        return from_input

    now = time.time()
    entry = _session_turn_store.get(session_id)
    prev = 0
    if entry and now - entry["lastUsed"] <= GROK_CLI_SESSION_TTL_SECONDS:
        prev = entry["turn"]

    # A new request advances the turn; full-history clients win via max().
    turn = max(from_input, prev + 1) if prev > 0 else from_input

    if len(_session_turn_store) >= GROK_CLI_TURN_STORE_MAX:
        oldest = min(
            _session_turn_store,
            key=lambda k: _session_turn_store[k]["lastUsed"],
        )
        _session_turn_store.pop(oldest, None)
    _session_turn_store[session_id] = {"turn": turn, "lastUsed": now}
    return turn


def _reset_turn_store() -> None:
    """Test helper — clear in-memory turn counters."""
    _session_turn_store.clear()


def resolve_session_id(body: dict, data: dict) -> str:
    """Stable session id: explicit client ids > per-connection > random."""
    for key in ("prompt_cache_key", "session_id", "conversation_id"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value
    metadata = body.get("metadata")
    if isinstance(metadata, dict):
        for key in ("session_id", "conversation_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
    # Clients without stable thread metadata share one connection session
    token = (data or {}).get("accessToken", "")
    if token:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"grok-cli:{token[:32]}"))
    return str(uuid.uuid4())


def resolve_agent_id(data: dict) -> str:
    """Stable agent id (x-grok-agent-id header)."""
    psd = (data or {}).get("providerSpecificData") or {}
    if psd.get("deviceId"):
        return str(psd["deviceId"])
    if psd.get("agentId"):
        return str(psd["agentId"])
    mid = uuid.uuid5(
        uuid.NAMESPACE_DNS, f"grok-cli-agent:{socket.gethostname()}",
    ).hex
    # Format as UUID-ish, mirroring the official CLI fingerprint
    return "-".join([
        mid[:8],
        mid[8:12],
        "5" + mid[13:16],
        "a" + mid[17:20],
        mid[:12].ljust(12, "0"),
    ])


# ── Chat Completions -> Responses API request ────────────────────────────


def _flatten_content_to_blocks(content: Any) -> list[dict]:
    """OpenAI chat content (str or multipart list) -> Responses blocks."""
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    if not isinstance(content, list):
        return [{"type": "input_text", "text": str(content or "")}]

    blocks: list[dict] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            blocks.append({"type": "input_text", "text": part.get("text", "")})
        elif part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            if url:
                blocks.append({
                    "type": "input_image",
                    "image_url": url,
                    "detail": (part.get("image_url") or {}).get(
                        "detail", "auto",
                    ),
                })
    return blocks


def chat_to_responses_request(body: dict) -> dict:
    """Convert a Chat Completions body to a Responses API body.

    Mirror of services.responses_translator.responses_to_chat_completions:
    system -> instructions, messages -> input items, tool_calls ->
    function_call items, tool messages -> function_call_output items.
    """
    result: dict[str, Any] = {}
    instructions_parts: list[str] = []
    input_items: list[dict] = []

    for message in body.get("messages", []):
        if not isinstance(message, dict):
            continue
        role = message.get("role", "user")
        content = message.get("content")

        if role in ("system", "developer"):
            if isinstance(content, str) and content:
                instructions_parts.append(content)
            continue

        if role == "tool":
            output = content if isinstance(content, str) else json.dumps(
                content, ensure_ascii=False,
            )
            input_items.append({
                "type": "function_call_output",
                "call_id": message.get("tool_call_id", ""),
                "output": output,
            })
            continue

        # user / assistant
        for tc in message.get("tool_calls", []) or []:
            func = tc.get("function", {}) or {}
            input_items.append({
                "type": "function_call",
                "call_id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": func.get("arguments", "{}"),
            })
        if content:
            input_items.append({
                "type": "message",
                "role": role,
                "content": _flatten_content_to_blocks(content),
            })

    result["input"] = input_items
    if instructions_parts:
        result["instructions"] = "\n\n".join(instructions_parts)

    # Pass through Responses-compatible fields
    for key in (
        "tools", "tool_choice", "temperature", "top_p",
        "max_output_tokens", "parallel_tool_calls", "text", "metadata",
        "prompt_cache_key", "reasoning", "include",
    ):
        if key in body:
            result[key] = body[key]

    if body.get("max_tokens") and "max_output_tokens" not in result:
        result["max_output_tokens"] = body["max_tokens"]
    if body.get("reasoning_effort"):
        result["reasoning_effort"] = body["reasoning_effort"]
    return result


# ── Responses input / tool normalization (port of executor) ──────────────


def _stringify_tool_output(output: Any) -> str:
    if isinstance(output, str):
        return output
    if output is None:
        return ""
    return json.dumps(output, ensure_ascii=False)


def _is_native_item_id(item_id: Any) -> bool:
    return isinstance(item_id, str) and bool(
        _NATIVE_ITEM_ID_RE.match(item_id)
    )


def _normalize_input_item(item: Any) -> dict | None:
    if not isinstance(item, dict):
        return item
    clean = {
        k: v for k, v in item.items()
        if k != "internal_chat_message_metadata_passthrough"
    }
    item_type = item.get("type")

    if item_type == "reasoning":
        if not _is_native_item_id(item.get("id")):
            return None
        if not isinstance(item.get("encrypted_content"), str):
            return None
        return clean

    if item_type == "custom_tool_call":
        call_id = item.get("call_id") or item.get("id")
        name = item.get("name", "").strip() if isinstance(
            item.get("name"), str,
        ) else ""
        if not call_id or not name:
            return None
        return {
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": json.dumps(
                {"input": _stringify_tool_output(
                    item.get("input", item.get("arguments")),
                )},
                ensure_ascii=False,
            ),
        }

    if item_type in ("custom_tool_call_output", "function_call_output"):
        call_id = item.get("call_id") or item.get("id")
        if not call_id:
            return None
        return {
            "type": "function_call_output",
            "call_id": call_id,
            "output": _stringify_tool_output(item.get("output")),
        }

    if item_type == "function_call":
        call_id = item.get("call_id") or item.get("id")
        name = item.get("name", "").strip() if isinstance(
            item.get("name"), str,
        ) else ""
        if not call_id or not name:
            return None
        normalized: dict[str, Any] = {"type": "function_call"}
        if _is_native_item_id(item.get("id")):
            normalized["id"] = item["id"]
        normalized["call_id"] = call_id
        normalized["name"] = name
        arguments = item.get("arguments")
        normalized["arguments"] = (
            arguments if isinstance(arguments, str)
            else json.dumps(arguments or {}, ensure_ascii=False)
        )
        if isinstance(item.get("status"), str):
            normalized["status"] = item["status"]
        return normalized

    return clean


def normalize_input(body: dict) -> None:
    """Normalize + filter Responses input items in place."""
    items = body.get("input")
    if not isinstance(items, list):
        return
    normalized = [
        n for n in (_normalize_input_item(i) for i in items) if n is not None
    ]
    call_ids = {
        item.get("call_id")
        for item in normalized
        if isinstance(item, dict)
        and item.get("type") == "function_call"
        and item.get("call_id")
    }
    body["input"] = [
        item for item in normalized
        if not (
            isinstance(item, dict)
            and item.get("type") == "function_call_output"
            and item.get("call_id") not in call_ids
        )
    ]


def strip_stored_item_references(body: dict) -> None:
    """Drop server ids that store=false cannot resolve."""
    items = body.get("input")
    if not isinstance(items, list):
        return
    kept: list[Any] = []
    for item in items:
        if isinstance(item, str):
            if _SERVER_ID_RE.match(item):
                continue
            kept.append(item)
            continue
        if isinstance(item, dict):
            if item.get("type") == "item_reference":
                continue
            item_id = item.get("id")
            if (
                isinstance(item_id, str)
                and _SERVER_ID_RE.match(item_id)
                and not _is_native_item_id(item_id)
            ):
                item.pop("id", None)
        kept.append(item)
    body["input"] = kept


def normalize_tools(body: dict) -> None:
    """Flatten Chat Completions tools to Responses format in place.

    Hosted tools (web_search / x_search / ...) pass through untouched.
    """
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        body.pop("tools", None)
        body.pop("tool_choice", None)
        return

    valid_names: set[str] = set()
    hosted_types: set[str] = set()
    flattened: list[dict] = []

    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_type = tool.get("type", "") if isinstance(
            tool.get("type"), str,
        ) else ""

        if tool_type in HOSTED_TOOL_TYPES:
            hosted_types.add(tool_type)
            flattened.append(tool)
            continue

        is_function = (
            tool_type == "function"
            or tool_type == ""
            or isinstance(tool.get("function"), dict)
            or isinstance(tool.get("name"), str)
        )
        if not is_function:
            continue

        func = tool.get("function") if isinstance(
            tool.get("function"), dict,
        ) else None
        raw_name = (
            tool.get("name") if isinstance(tool.get("name"), str)
            else (func or {}).get("name", "")
        )
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        if not name:
            continue

        description = (
            tool.get("description")
            if isinstance(tool.get("description"), str)
            else (func or {}).get("description", "")
        )
        if tool_type == "custom":
            parameters = dict(GROK_CLI_FREEFORM_TOOL_PARAMETERS)
        elif isinstance(tool.get("parameters"), dict):
            parameters = tool["parameters"]
        elif isinstance((func or {}).get("parameters"), dict):
            parameters = func["parameters"]
        else:
            parameters = {"type": "object", "properties": {}}

        new_tool: dict[str, Any] = {"type": "function", "name": name[:128]}
        if description:
            new_tool["description"] = description
        new_tool["parameters"] = parameters
        flattened.append(new_tool)
        valid_names.add(name[:128])

    if not flattened:
        body.pop("tools", None)
        body.pop("tool_choice", None)
        return
    body["tools"] = flattened

    choice = body.get("tool_choice")
    if isinstance(choice, dict):
        choice_type = choice.get("type", "") if isinstance(
            choice.get("type"), str,
        ) else ""
        if choice_type in ("function", "custom"):
            raw = choice.get("name") or (choice.get("function") or {}).get(
                "name",
            )
            name = raw.strip()[:128] if isinstance(raw, str) else ""
            if name and name in valid_names:
                body["tool_choice"] = {"type": "function", "name": name}
            else:
                body.pop("tool_choice", None)
        elif choice_type not in hosted_types:
            body.pop("tool_choice", None)


# ── Main request builder ─────────────────────────────────────────────────


def build_grok_cli_request(
    model: str, body: dict, data: dict,
) -> tuple[dict, dict]:
    """Build the Responses API request body + per-request header metadata.

    Args:
        model: Resolved model id (e.g. "grok-build", "grok-4.5-high").
        body: Client request body (Chat Completions or Responses format).
        data: Connection data blob (accessToken, providerSpecificData...).

    Returns:
        (transformed_body, meta) where meta carries sessionId, reqId,
        turnIdx, agentId and the upstream model id.
    """
    from app.services.responses_translator import normalize_responses_input

    if "messages" in body and "input" not in body:
        result: dict = chat_to_responses_request(body)
    else:
        result = dict(body)

    input_items = normalize_responses_input(result.get("input"))
    if input_items is None:
        input_items = [{
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "..."}],
        }]
    result["input"] = input_items
    result.pop("messages", None)

    # Keep role:"system" as-is in input — official CLI sends system, not
    # developer. normalize/strip/tool passes mirror the executor order.
    normalize_input(result)
    strip_stored_item_references(result)
    normalize_tools(result)

    session_id = resolve_session_id(result, data)
    meta = {
        "sessionId": session_id,
        "reqId": str(uuid.uuid4()),
        "turnIdx": resolve_turn_idx(session_id, result.get("input")),
        "agentId": resolve_agent_id(data),
    }

    result["stream"] = True
    result["store"] = False

    # Resolve upstream model id (strip effort suffix, e.g. grok-4.5-high)
    model_effort = resolve_effort_from_model(model)
    upstream_model = model
    if model_effort:
        upstream_model = model[: -(len(model_effort) + 1)]
    result["model"] = upstream_model
    meta["model"] = upstream_model

    # Reasoning effort priority: explicit > reasoning_effort > model
    # suffix > default high. grok-build rejects effort but accepts
    # summary/encrypted continuity.
    supports = supports_reasoning_effort(upstream_model)
    reasoning = result.get("reasoning")
    if not isinstance(reasoning, dict):
        reasoning = {"summary": "concise"}
        if supports:
            reasoning["effort"] = normalize_effort(
                result.get("reasoning_effort") or model_effort,
            )
        result["reasoning"] = reasoning
    else:
        if supports:
            reasoning["effort"] = normalize_effort(
                reasoning.get("effort")
                or result.get("reasoning_effort")
                or model_effort,
            )
        else:
            reasoning.pop("effort", None)
        reasoning.setdefault("summary", "concise")
    result.pop("reasoning_effort", None)

    # Encrypted reasoning for multi-turn continuity (CLI always asks)
    if result.get("reasoning", {}).get("effort") != "none":
        include = result.get("include")
        include = include if isinstance(include, list) else []
        if "reasoning.encrypted_content" not in include:
            include.append("reasoning.encrypted_content")
        result["include"] = include

    if (
        result.get("max_tokens")
        and "max_output_tokens" not in result
    ):
        result["max_output_tokens"] = result["max_tokens"]

    # Drop Chat Completions leftovers the Responses API rejects
    for key in _CHAT_LEFTOVERS:
        result.pop(key, None)

    # Enforce the Responses API allowlist
    for key in list(result.keys()):
        if key not in RESPONSES_API_ALLOWLIST:
            result.pop(key)

    return result, meta


# ── Responses API response -> Chat Completions ───────────────────────────


def _extract_reasoning_summary(item: dict) -> str:
    """Collect reasoning summary text from a reasoning output item."""
    parts: list[str] = []
    summary = item.get("summary")
    if isinstance(summary, list):
        for block in summary:
            if isinstance(block, dict) and block.get("text"):
                parts.append(block["text"])
    return "\n".join(parts)


def responses_to_openai_response(resp: dict, model: str = "") -> dict:
    """Convert a final Responses API object to Chat Completions JSON."""
    output = resp.get("output", [])
    if not isinstance(output, list):
        output = []

    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[dict] = []

    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "message":
            for part in item.get("content", []) or []:
                if isinstance(part, dict) and (
                    part.get("type") == "output_text"
                ):
                    text_parts.append(part.get("text", ""))
        elif item_type == "reasoning":
            summary = _extract_reasoning_summary(item)
            if summary:
                reasoning_parts.append(summary)
        elif item_type == "function_call":
            tool_calls.append({
                "id": item.get("call_id") or item.get("id", ""),
                "type": "function",
                "function": {
                    "name": item.get("name", ""),
                    "arguments": item.get("arguments", "{}"),
                },
            })

    status = resp.get("status", "completed")
    if tool_calls:
        finish_reason = "tool_calls"
    elif status == "incomplete":
        finish_reason = "length"
    else:
        finish_reason = "stop"

    message: dict[str, Any] = {
        "role": "assistant",
        "content": "".join(text_parts) or None,
    }
    if reasoning_parts:
        message["reasoning_content"] = "\n".join(reasoning_parts)
    if tool_calls:
        message["tool_calls"] = tool_calls

    usage = resp.get("usage", {}) or {}
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)

    resp_id = str(resp.get("id", "")).replace("resp_", "")
    return {
        "id": f"chatcmpl-{resp_id}" if resp_id else (
            f"chatcmpl-{uuid.uuid4().hex[:29]}"
        ),
        "object": "chat.completion",
        "created": resp.get("created_at") or int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": usage.get(
                "total_tokens", prompt_tokens + completion_tokens,
            ),
        },
    }
