"""Claude Messages API ↔ OpenAI Chat Completions format translator.

Handles bidirectional translation for non-streaming requests.
Streaming translation is in Task 23.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Claude → OpenAI request translation
# ─────────────────────────────────────────────────────────────────────────────


def _flatten_content(content: str | list[dict]) -> str:
    """Flatten Claude content blocks to a plain string.

    Claude allows content to be a string or a list of typed blocks
    (text, image, tool_use, tool_result, etc.). OpenAI expects a string
    or a list of typed parts — for simplicity we flatten to string.
    """
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "tool_result":
                # Tool results contain content blocks
                inner = block.get("content", "")
                if isinstance(inner, list):
                    parts.extend(
                        b.get("text", "") for b in inner if b.get("type") == "text"
                    )
                elif isinstance(inner, str):
                    parts.append(inner)
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts) if parts else ""


def claude_to_openai_request(body: dict[str, Any]) -> dict[str, Any]:
    """Translate a Claude Messages API request to OpenAI Chat Completions format.

    Claude Messages API:
      {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "system": "You are helpful",  // optional
        "messages": [
          {"role": "user", "content": "Hello"},
          {"role": "assistant", "content": "Hi!"},
          {"role": "user", "content": [{"type": "text", "text": "Bye"}]}
        ],
        "temperature": 0.7,
        "stop_sequences": ["END"],
        "stream": false,
      }

    OpenAI Chat Completions:
      {
        "model": "gpt-4",
        "messages": [
          {"role": "system", "content": "You are helpful"},
          {"role": "user", "content": "Hello"},
          {"role": "assistant", "content": "Hi!"},
          {"role": "user", "content": "Bye"}
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
        "stop": ["END"],
        "stream": false,
      }
    """
    messages: list[dict[str, str]] = []

    # System message
    system = body.get("system")
    if system:
        system_text = _flatten_content(system)
        if system_text:
            messages.append({"role": "system", "content": system_text})

    # Messages
    for msg in body.get("messages", []):
        role = msg.get("role", "user")
        content = _flatten_content(msg.get("content", ""))

        # Map Claude roles to OpenAI roles
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            messages.append({"role": "assistant", "content": content})

    out: dict[str, Any] = {
        "model": body.get("model", ""),
        "messages": messages,
        "max_tokens": body.get("max_tokens", 4096),
    }

    # Optional fields
    if "temperature" in body:
        out["temperature"] = body["temperature"]
    if "top_p" in body:
        out["top_p"] = body["top_p"]
    if "stop_sequences" in body:
        out["stop"] = body["stop_sequences"]
    if "stream" in body:
        out["stream"] = body["stream"]

    return out


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI → Claude response translation
# ─────────────────────────────────────────────────────────────────────────────

_FINISH_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}


def openai_to_claude_response(
    data: dict[str, Any],
    *,
    model: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Translate an OpenAI Chat Completions response to Claude Messages API format.

    OpenAI response:
      {
        "id": "chatcmpl-xxx",
        "object": "chat.completion",
        "model": "gpt-4",
        "choices": [{
          "index": 0,
          "message": {"role": "assistant", "content": "Hello!"},
          "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
      }

    Claude response:
      {
        "id": "msg_xxx",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Hello!"}],
        "model": "claude-3-5-sonnet-20241022",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5}
      }
    """
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "stop")
    usage = data.get("usage", {})

    # Build content blocks
    content_text = message.get("content", "")
    content: list[dict[str, Any]] = []
    if content_text:
        content.append({"type": "text", "text": content_text})

    # Handle tool_calls if present
    tool_calls = message.get("tool_calls")
    if tool_calls:
        for tc in tool_calls:
            fn = tc.get("function", {})
            content.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": fn.get("name", ""),
                "input": json.loads(fn.get("arguments", "{}")),
            })

    return {
        "id": data.get("id") or f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": model,
        "stop_reason": _FINISH_REASON_MAP.get(finish_reason, "end_turn"),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI SSE → Claude SSE streaming translation
# ─────────────────────────────────────────────────────────────────────────────


def claude_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a Claude SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


class ClaudeStreamTranslator:
    """Stateful translator from OpenAI SSE stream to Claude SSE stream.

    Usage:
        translator = ClaudeStreamTranslator(model="claude-3-5-sonnet")
        for openai_line in upstream_sse_lines:
            claude_events = translator.feed(openai_line)
            for event in claude_events:
                yield event
    """

    def __init__(self, model: str, request_id: str | None = None):
        self.model = model
        self.request_id = request_id or f"msg_{uuid.uuid4().hex[:24]}"
        self._started = False
        self._block_started = False
        self._finished = False
        self._input_tokens = 0
        self._output_tokens = 0

    def feed(self, line: str) -> list[str]:
        """Process one SSE line from OpenAI upstream. Returns Claude SSE events.

        Args:
            line: A raw SSE line (e.g. 'data: {...}' or 'data: [DONE]')

        Returns:
            List of formatted Claude SSE event strings.
        """
        # Parse the SSE line
        if not line.startswith("data: "):
            return []

        data_str = line[6:].strip()
        if data_str == "[DONE]":
            return self._finish()

        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return []

        events: list[str] = []

        # Emit message_start on first chunk
        if not self._started:
            events.append(claude_sse_event("message_start", {
                "type": "message_start",
                "message": {
                    "id": self.request_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": self.model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": self._input_tokens, "output_tokens": 0},
                },
            }))
            self._started = True

        # Extract usage if present
        usage = data.get("usage")
        if usage:
            self._input_tokens = usage.get("prompt_tokens", self._input_tokens)
            self._output_tokens = usage.get("completion_tokens", self._output_tokens)

        # Process choices
        choices = data.get("choices", [])
        if not choices:
            return events

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        # Content delta
        content = delta.get("content")
        if content:
            # Start content block if not started
            if not self._block_started:
                events.append(claude_sse_event("content_block_start", {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                }))
                self._block_started = True

            events.append(claude_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": content},
            }))

        # Finish reason → end the stream
        if finish_reason and not self._finished:
            # Close content block if it was opened
            if self._block_started:
                events.append(claude_sse_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": 0,
                }))

            stop_reason = _FINISH_REASON_MAP.get(finish_reason, "end_turn")
            events.append(claude_sse_event("message_delta", {
                "type": "message_delta",
                "delta": {
                    "stop_reason": stop_reason,
                    "stop_sequence": None,
                },
                "usage": {
                    "input_tokens": self._input_tokens,
                    "output_tokens": self._output_tokens,
                },
            }))
            events.append(claude_sse_event("message_stop", {
                "type": "message_stop",
            }))
            self._finished = True

        return events

    def _finish(self) -> list[str]:
        """Handle [DONE] — emit closing events if not already finished."""
        if self._finished:
            return []

        events: list[str] = []
        if self._block_started:
            events.append(claude_sse_event("content_block_stop", {
                "type": "content_block_stop",
                "index": 0,
            }))
        events.append(claude_sse_event("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
            },
        }))
        events.append(claude_sse_event("message_stop", {
            "type": "message_stop",
        }))
        self._finished = True
        return events
