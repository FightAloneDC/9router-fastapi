"""OpenAI Responses API ↔ Chat Completions format translator.

Handles bidirectional translation for both non-streaming and streaming requests.

Phase 1: Request translator (Responses API → Chat Completions)
Phase 2: Response translator (Chat Completions → Responses API)
Phase 2b: Streaming translator (Chat Completions SSE → Responses API SSE)
"""

from __future__ import annotations

import json
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Request translator (Responses API → Chat Completions)
# ─────────────────────────────────────────────────────────────────────────────


def normalize_responses_input(input_data: Any) -> list[dict] | None:
    """Normalize Responses API input to array format.

    Accepts string or array. Returns array of message items.
    Empty input injects placeholder (providers require at least one user message).
    """
    if isinstance(input_data, str):
        text = input_data.strip() or "..."
        return [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}]

    if isinstance(input_data, list):
        if len(input_data) == 0:
            return [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "..."}]}]
        return input_data

    return None


def _convert_content_blocks(content: Any, role: str) -> str | list:
    """Convert Responses API content blocks to Chat Completions format."""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return str(content) if content else ""

    text_parts: list[str] = []
    for block in content:
        block_type = block.get("type", "") if isinstance(block, dict) else ""

        if block_type in ("input_text", "output_text"):
            text_parts.append(block.get("text", ""))
        elif block_type == "input_image":
            url = block.get("image_url") or block.get("file_id", "")
            return [{"type": "image_url", "image_url": {"url": url, "detail": block.get("detail", "auto")}}]
        else:
            text = block.get("text") or block.get("content") or json.dumps(block)
            text_parts.append(str(text))

    return "\n".join(text_parts) if text_parts else ""


def _extract_reasoning_text(item: dict) -> str:
    """Extract reasoning text from a reasoning item."""
    if isinstance(item.get("summary"), list):
        text = "\n".join(s.get("text", "") for s in item["summary"] if isinstance(s, dict))
        if text:
            return text

    if isinstance(item.get("content"), list):
        text = "\n".join(c.get("text", "") for c in item["content"] if isinstance(c, dict))
        if text:
            return text

    return ""


def _normalize_tool_params(params: dict | None) -> dict:
    """Ensure tool parameters always have properties field."""
    if not params:
        return {"type": "object", "properties": {}}
    if params.get("type") == "object" and "properties" not in params:
        return {**params, "properties": {}}
    return params


def responses_to_chat_completions(body: dict) -> dict:
    """Convert OpenAI Responses API request to Chat Completions format.

    Key transformations:
    - instructions → system message
    - input[] → messages[]
    - input_text/output_text → text content
    - input_image → image_url content
    - function_call → tool_calls
    - function_call_output → tool message
    - reasoning → buffered and attached to next assistant message
    - tools format: { name, parameters } → { function: { name, parameters } }
    """
    if "input" not in body:
        return body  # Already in Chat Completions format

    result = {**body}
    result["messages"] = []

    # instructions → system message
    if body.get("instructions"):
        result["messages"].append({"role": "system", "content": body["instructions"]})

    # Parse input items
    input_items = normalize_responses_input(body["input"])
    if input_items is None:
        return body

    current_assistant_msg: dict | None = None
    pending_reasoning = ""

    for item in input_items:
        item_type = item.get("type") or ("message" if "role" in item else None)

        if item_type == "message":
            # Flush pending assistant message
            if current_assistant_msg:
                result["messages"].append(current_assistant_msg)
                current_assistant_msg = None

            # Convert content blocks
            content = _convert_content_blocks(item.get("content", []), item.get("role", "user"))

            msg: dict[str, Any] = {"role": item.get("role", "user"), "content": content}

            # Attach buffered reasoning to assistant messages
            if item.get("role") == "assistant" and pending_reasoning:
                msg["reasoning_content"] = pending_reasoning
                pending_reasoning = ""

            result["messages"].append(msg)

        elif item_type == "function_call":
            # Build assistant message with tool_calls
            if not current_assistant_msg:
                current_assistant_msg = {"role": "assistant", "content": None, "tool_calls": []}
                if pending_reasoning:
                    current_assistant_msg["reasoning_content"] = pending_reasoning
                    pending_reasoning = ""

            name = item.get("name", "")
            if name and name.strip():
                current_assistant_msg["tool_calls"].append({
                    "id": item.get("call_id", ""),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": item.get("arguments", "{}"),
                    },
                })

        elif item_type == "function_call_output":
            # Flush assistant message first
            if current_assistant_msg:
                result["messages"].append(current_assistant_msg)
                current_assistant_msg = None

            output = item.get("output", "")
            if not isinstance(output, str):
                output = json.dumps(output)

            result["messages"].append({
                "role": "tool",
                "tool_call_id": item.get("call_id", ""),
                "content": output,
            })

        elif item_type == "reasoning":
            # Buffer reasoning text for next assistant message
            text = _extract_reasoning_text(item)
            if text:
                pending_reasoning = f"{pending_reasoning}\n{text}" if pending_reasoning else text

    # Flush remaining
    if current_assistant_msg:
        result["messages"].append(current_assistant_msg)

    # Convert tools format
    if "tools" in body and isinstance(body["tools"], list):
        result["tools"] = []
        for tool in body["tools"]:
            if "function" in tool:
                result["tools"].append(tool)  # Already Chat Completions format
            elif tool.get("name"):
                result["tools"].append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": _normalize_tool_params(tool.get("parameters")),
                    },
                })

    # Cleanup Responses API specific fields
    for field in ["input", "instructions", "include", "store", "reasoning", "prompt_cache_key"]:
        result.pop(field, None)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Response translator (Chat Completions → Responses API)
# ─────────────────────────────────────────────────────────────────────────────


def chat_completions_to_responses(data: dict, model: str = "") -> dict:
    """Convert OpenAI Chat Completions response to Responses API format."""
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "stop")

    # Map finish_reason → status
    status_map = {
        "stop": "completed",
        "length": "incomplete",
        "tool_calls": "completed",
    }
    status = status_map.get(finish_reason, "completed")

    # Build output items
    output: list[dict[str, Any]] = []

    # Message output
    content_blocks: list[dict[str, Any]] = []
    if message.get("content"):
        content_blocks.append({
            "type": "output_text",
            "annotations": [],
            "text": message["content"],
        })

    # Tool calls → function_call outputs
    for tc in message.get("tool_calls", []):
        func = tc.get("function", {})
        output.append({
            "type": "function_call",
            "id": tc.get("id", ""),
            "call_id": tc.get("id", ""),
            "name": func.get("name", ""),
            "arguments": func.get("arguments", "{}"),
        })

    if content_blocks:
        output.append({
            "type": "message",
            "id": data.get("id", "").replace("chatcmpl-", "msg_"),
            "role": "assistant",
            "content": content_blocks,
            "status": "completed",
        })

    # Usage
    usage = data.get("usage", {})

    return {
        "id": data.get("id", "").replace("chatcmpl-", "resp_"),
        "object": "response",
        "created_at": data.get("created", 0),
        "status": status,
        "model": model or data.get("model", ""),
        "output": output,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2b: Streaming translator (Chat Completions SSE → Responses API SSE)
# ─────────────────────────────────────────────────────────────────────────────


class ResponsesStreamTranslator:
    """Translates Chat Completions SSE chunks to Responses API SSE events."""

    def __init__(self, model: str = ""):
        self.model = model
        self.seq = 0
        self.started = False
        self.response_id = ""
        self.created = 0
        self.full_text = ""
        self.tool_calls: dict[int, dict] = {}  # index → {id, name, arguments}
        self._output_item_added = False
        self._finished = False
        self._next_output_index = 0
        self._message_output_index: int | None = None
        self._tool_output_index: dict[int, int] = {}
        self._tool_item_started: set[int] = set()
        self._output_items: list[dict] = []

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def emit(self, event_type: str, data: dict) -> dict:
        data["sequence_number"] = self.next_seq()
        return {"event": event_type, "data": data}

    def translate_chunk(self, chunk: dict) -> list[dict]:
        """Translate a single Chat Completions chunk to Responses API events."""
        events: list[dict] = []

        if not chunk.get("choices"):
            return events

        choice = chunk["choices"][0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        # Start events (emit once)
        if not self.started:
            self.started = True
            self.response_id = f"resp_{chunk.get('id', 'unknown')}"
            self.created = chunk.get("created", 0)

            events.append(self.emit("response.created", {
                "type": "response.created",
                "response": {
                    "id": self.response_id,
                    "object": "response",
                    "created_at": self.created,
                    "status": "in_progress",
                    "output": [],
                },
            }))

            events.append(self.emit("response.in_progress", {
                "type": "response.in_progress",
                "response": {"id": self.response_id, "status": "in_progress"},
            }))

        # Text content delta
        if delta.get("content"):
            if not self._output_item_added:
                self._output_item_added = True
                self._message_output_index = self._next_output_index
                self._next_output_index += 1
                events.append(self.emit("response.output_item.added", {
                    "type": "response.output_item.added",
                    "output_index": self._message_output_index,
                    "item": {
                        "type": "message",
                        "id": f"msg_{self.response_id}",
                        "role": "assistant",
                        "content": [],
                        "status": "in_progress",
                    },
                }))
                events.append(self.emit("response.content_part.added", {
                    "type": "response.content_part.added",
                    "output_index": self._message_output_index,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": ""},
                }))

            self.full_text += delta["content"]
            events.append(self.emit("response.output_text.delta", {
                "type": "response.output_text.delta",
                "output_index": self._message_output_index,
                "content_index": 0,
                "delta": delta["content"],
            }))

        # Tool calls — stream as Responses function_call items
        for tc in delta.get("tool_calls", []):
            idx = tc.get("index", 0)
            func = tc.get("function", {}) or {}

            if idx not in self.tool_calls:
                self.tool_calls[idx] = {
                    "id": tc.get("id", "") or f"call_{idx}",
                    "name": "",
                    "arguments": "",
                }

            if tc.get("id"):
                self.tool_calls[idx]["id"] = tc["id"]
            if func.get("name"):
                self.tool_calls[idx]["name"] = func["name"]

            arg_delta = func.get("arguments") or ""
            if arg_delta:
                self.tool_calls[idx]["arguments"] += arg_delta

            if idx not in self._tool_item_started:
                self._tool_item_started.add(idx)
                out_idx = self._next_output_index
                self._next_output_index += 1
                self._tool_output_index[idx] = out_idx
                call_id = self.tool_calls[idx]["id"]
                events.append(self.emit("response.output_item.added", {
                    "type": "response.output_item.added",
                    "output_index": out_idx,
                    "item": {
                        "type": "function_call",
                        "id": call_id,
                        "call_id": call_id,
                        "name": self.tool_calls[idx]["name"],
                        "arguments": "",
                        "status": "in_progress",
                    },
                }))

            if arg_delta:
                out_idx = self._tool_output_index[idx]
                events.append(self.emit(
                    "response.function_call_arguments.delta",
                    {
                        "type": "response.function_call_arguments.delta",
                        "output_index": out_idx,
                        "item_id": self.tool_calls[idx]["id"],
                        "delta": arg_delta,
                    },
                ))

        # Finish
        if finish_reason:
            events.extend(self._flush_finish(finish_reason, chunk))

        return events

    def _flush_finish(self, finish_reason: str, chunk: dict) -> list[dict]:
        """Emit completion events."""
        if self._finished:
            return []
        self._finished = True
        events: list[dict] = []
        output: list[dict] = []

        # Flush text output
        if self.full_text and self._output_item_added:
            msg_idx = self._message_output_index or 0
            events.append(self.emit("response.output_text.done", {
                "type": "response.output_text.done",
                "output_index": msg_idx,
                "content_index": 0,
                "text": self.full_text,
            }))
            events.append(self.emit("response.content_part.done", {
                "type": "response.content_part.done",
                "output_index": msg_idx,
                "content_index": 0,
                "part": {"type": "output_text", "text": self.full_text},
            }))
            message_item = {
                "type": "message",
                "id": f"msg_{self.response_id}",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": self.full_text,
                }],
                "status": "completed",
            }
            events.append(self.emit("response.output_item.done", {
                "type": "response.output_item.done",
                "output_index": msg_idx,
                "item": message_item,
            }))
            output.append(message_item)

        # Flush tool calls
        for idx in sorted(self.tool_calls.keys()):
            tc = self.tool_calls[idx]
            out_idx = self._tool_output_index.get(idx)
            if out_idx is None:
                out_idx = self._next_output_index
                self._next_output_index += 1
                self._tool_output_index[idx] = out_idx
                events.append(self.emit("response.output_item.added", {
                    "type": "response.output_item.added",
                    "output_index": out_idx,
                    "item": {
                        "type": "function_call",
                        "id": tc["id"],
                        "call_id": tc["id"],
                        "name": tc["name"],
                        "arguments": "",
                        "status": "in_progress",
                    },
                }))

            events.append(self.emit(
                "response.function_call_arguments.done",
                {
                    "type": "response.function_call_arguments.done",
                    "output_index": out_idx,
                    "item_id": tc["id"],
                    "arguments": tc["arguments"],
                },
            ))
            tool_item = {
                "type": "function_call",
                "id": tc["id"],
                "call_id": tc["id"],
                "name": tc["name"],
                "arguments": tc["arguments"],
                "status": "completed",
            }
            events.append(self.emit("response.output_item.done", {
                "type": "response.output_item.done",
                "output_index": out_idx,
                "item": tool_item,
            }))
            output.append(tool_item)

        self._output_items = output

        # Final completed event — output MUST carry items for clients
        usage = chunk.get("usage", {})
        events.append(self.emit("response.completed", {
            "type": "response.completed",
            "response": {
                "id": self.response_id,
                "object": "response",
                "created_at": self.created,
                "status": "completed",
                "model": self.model,
                "output": output,
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            },
        }))

        return events

    def finalize(self, usage: dict | None = None) -> list[dict]:
        """Emit response.completed if stream ended without finish_reason.

        Call on ``data: [DONE]`` or when the upstream SSE closes. Idempotent.
        """
        if self._finished:
            return []
        if not self.started:
            self.started = True
            self.response_id = self.response_id or "resp_unknown"
            events = [
                self.emit("response.created", {
                    "type": "response.created",
                    "response": {
                        "id": self.response_id,
                        "object": "response",
                        "created_at": self.created,
                        "status": "in_progress",
                        "output": [],
                    },
                }),
            ]
            events.extend(
                self._flush_finish("stop", {"usage": usage or {}}),
            )
            return events
        return self._flush_finish("stop", {"usage": usage or {}})


def build_incomplete_terminal_sse(
    *,
    response_id: str,
    model: str = "",
) -> str:
    """SSE payload for Responses clients when upstream closed early.

    OpenAI SDKs require a terminal event (completed / failed / incomplete /
    cancelled). Without one they raise:
    \"stream closed before a terminal response event was received\".
    """
    data = {
        "type": "response.incomplete",
        "response": {
            "id": response_id,
            "object": "response",
            "status": "incomplete",
            "model": model,
            "output": [],
            "incomplete_details": {
                "reason": "upstream_stream_closed",
            },
        },
    }
    return (
        f"event: response.incomplete\n"
        f"data: {json.dumps(data)}\n\n"
    )
