"""Morph handler — Apply XML I/O + tool_call conversion.

Request: sanitize (Apply merge XML, or Apply tools with
tool_choice=none). Response: unwrap XML; convert Apply
``<tool_call>`` content into OpenAI ``tool_calls`` (incl. SSE).
"""

from __future__ import annotations

import json

from app.providers.base import BaseProviderConfig, BaseProviderHandler
# from app.providers.morph.debug_io import save_provider_response
from app.providers.morph.transform import (
    MorphSseToolState,
    apply_fast_completion,
    client_bash_tool_name,
    flatten_content,
    last_user_text,
    model_tail,
    normalize_message,
    normalize_morph_completion,
    normalize_morph_sse_line,
    sanitize_morph_chat_body,
)

# Re-export for existing unit tests.
adapt_morph_body = sanitize_morph_chat_body

__all__ = [
    "MorphHandler",
    "adapt_morph_body",
    "flatten_content",
]


class MorphHandler(BaseProviderHandler):
    """Adapt client messages to Morph Apply / Warp / Fast contracts."""

    SSE_LINE_TRANSFORM = True

    def __init__(self, config: BaseProviderConfig) -> None:
        super().__init__(config)
        self._sse_tool_state = MorphSseToolState()
        # self._sse_raw: list[str] = []

    async def prepare_request(
        self,
        headers: dict[str, str],
        body: dict,
        stream: bool = False,
    ) -> tuple[dict[str, str], dict]:
        del stream
        self._sse_tool_state = MorphSseToolState()
        messages = body.get("messages")
        if isinstance(messages, list):
            cleaned = [normalize_message(m) for m in messages]
            self._sse_tool_state.last_user = last_user_text(cleaned)
        self._sse_tool_state.bash_tool = client_bash_tool_name(body)
        self._sse_tool_state.apply_fast = (
            model_tail(body.get("model")) == "morph-v3-fast"
        )
        return {**headers}, sanitize_morph_chat_body(body)

    def unwrap_response(self, response_text: str) -> dict:
        """Parse JSON; convert Apply <tool_call> XML → tool_calls."""
        # save_provider_response(response_text)
        data = json.loads(response_text)
        if not isinstance(data, dict):
            return data
        data = normalize_morph_completion(data)
        if self._sse_tool_state.apply_fast:
            data = apply_fast_completion(
                data,
                last_user=self._sse_tool_state.last_user,
                bash_tool=self._sse_tool_state.bash_tool,
            )
        return data

    def transform_openai_sse_line(self, line: str) -> str | None:
        """Buffer streamed <tool_call> XML into OpenAI tool_calls."""
        # self._sse_raw.append(line.rstrip("\n"))
        # stripped = line.strip()
        # if (
        #     stripped == "data: [DONE]"
        #     or "finish_reason" in stripped
        #     or (
        #         stripped.startswith("data:")
        #         and '"usage"' in stripped
        #         and '"choices"' not in stripped
        #     )
        # ):
        #     save_provider_response("\n".join(self._sse_raw) + "\n")
        return normalize_morph_sse_line(line, self._sse_tool_state)

    def should_fallback_on_error(
        self,
        status_code: int,
        error_text: str,
    ) -> bool | None:
        """Do not rotate the farm on a body Morph cannot parse."""
        del status_code
        lower = (error_text or "").lower()
        if "charcodeat" in lower:
            return False
        return None
