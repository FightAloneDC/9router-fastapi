"""Grok CLI upstream stream translation.

Translates Responses API SSE events from cli-chat-proxy.grok.com into
OpenAI Chat Completions SSE chunks (mirror of ClaudeStreamTranslator /
OpenaiStreamTranslator in services/message_translator.py).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


class ResponsesUpstreamTranslator:
    """Responses API SSE -> OpenAI Chat Completions SSE.

    feed() accepts one raw SSE line and returns a list of ready-to-yield
    SSE strings ("data: {...}\\n\\n" and finally "data: [DONE]\\n\\n").
    """

    def __init__(self, model: str = "", request_id: str = ""):
        self.model = model
        self.request_id = request_id or (
            f"chatcmpl-{uuid.uuid4().hex[:29]}"
        )
        self.created = int(time.time())
        self.started = False
        self.finished = False
        self.tool_count = 0
        self.tool_index_by_item: dict[str, int] = {}
        self.usage: dict = {}

    # ── Public API ─────────────────────────────────────────────────────

    def feed(self, raw_line: str) -> list[str]:
        line = raw_line.strip()
        if not line or line.startswith(":") or line.startswith("event:"):
            return []
        if not line.startswith("data:"):
            return []
        data_str = line[5:].strip()
        if not data_str or data_str == "[DONE]":
            return []
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            return []
        if not isinstance(event, dict):
            return []
        return self._translate_event(event)

    # ── Event translation ──────────────────────────────────────────────

    def _translate_event(self, event: dict) -> list[str]:
        event_type = event.get("type", "")
        out: list[str] = []

        if event_type == "response.created":
            out.extend(self._ensure_started())

        elif event_type == "response.output_text.delta":
            delta = event.get("delta") or ""
            if delta:
                out.extend(self._ensure_started())
                out.append(self._chunk({"content": delta}))

        elif event_type == "response.reasoning_summary_text.delta":
            delta = event.get("delta") or ""
            if delta:
                out.extend(self._ensure_started())
                out.append(self._chunk({"reasoning_content": delta}))

        elif event_type == "response.output_item.added":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                out.extend(self._ensure_started())
                out.append(self._start_tool_call(item))

        elif event_type == "response.function_call_arguments.delta":
            item_id = event.get("item_id", "")
            index = self.tool_index_by_item.get(item_id)
            delta = event.get("delta") or ""
            if index is not None and delta:
                out.append(self._chunk({"tool_calls": [{
                    "index": index,
                    "function": {"arguments": delta},
                }]}))

        elif event_type == "response.output_item.done":
            # Safety net: some upstreams emit only the done event for a
            # function_call (full arguments, no added/delta events).
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                item_id = item.get("id") or item.get("call_id") or ""
                if item_id and item_id not in self.tool_index_by_item:
                    out.extend(self._ensure_started())
                    out.append(self._start_tool_call(item))
                    index = self.tool_index_by_item[item_id]
                    arguments = item.get("arguments") or ""
                    if arguments:
                        out.append(self._chunk({"tool_calls": [{
                            "index": index,
                            "function": {"arguments": arguments},
                        }]}))

        elif event_type == "response.completed":
            response = event.get("response") or {}
            usage = response.get("usage") or {}
            if usage:
                prompt_tokens = usage.get("input_tokens", 0)
                completion_tokens = usage.get("output_tokens", 0)
                self.usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": usage.get(
                        "total_tokens",
                        prompt_tokens + completion_tokens,
                    ),
                }
            out.extend(self._finish(response.get("status")))

        elif event_type in ("response.failed", "error"):
            error = event.get("error") or (
                event.get("response") or {}
            ).get("error") or {}
            message = error.get("message") or json.dumps(event)[:300]
            out.append(_sse({
                "error": {"message": message, "type": "responses_error"},
            }))
            out.extend(self._finish("failed"))

        return out

    # ── Chunk builders ─────────────────────────────────────────────────

    def _ensure_started(self) -> list[str]:
        if self.started:
            return []
        self.started = True
        return [self._chunk({"role": "assistant", "content": ""})]

    def _start_tool_call(self, item: dict) -> str:
        item_id = item.get("id") or item.get("call_id") or ""
        index = self.tool_count
        self.tool_count += 1
        if item_id:
            self.tool_index_by_item[item_id] = index
        return self._chunk({"tool_calls": [{
            "index": index,
            "id": item.get("call_id") or item_id,
            "type": "function",
            "function": {
                "name": item.get("name", ""),
                "arguments": "",
            },
        }]})

    def _chunk(
        self, delta: dict, finish_reason: str | None = None,
        usage: dict | None = None,
    ) -> str:
        choice: dict[str, Any] = {"index": 0, "delta": delta}
        if finish_reason:
            choice["finish_reason"] = finish_reason
        payload: dict[str, Any] = {
            "id": self.request_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [choice],
        }
        if usage:
            payload["usage"] = usage
        return _sse(payload)

    def _finish(self, status: str | None) -> list[str]:
        if self.finished:
            return []
        self.finished = True
        if self.tool_count > 0:
            finish_reason = "tool_calls"
        elif status == "incomplete":
            finish_reason = "length"
        else:
            finish_reason = "stop"
        out = [self._chunk({}, finish_reason=finish_reason)]
        if self.usage:
            out.append(self._chunk({}, usage=self.usage))
        out.append("data: [DONE]\n\n")
        return out
