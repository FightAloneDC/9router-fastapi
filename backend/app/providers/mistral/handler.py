"""Mistral handler — sanitize body + PS fallback policy."""

from __future__ import annotations

import json

from app.providers.base import BaseProviderHandler
from app.providers.mistral.models import fetch_models as mistral_fetch_models
from app.providers.mistral.transform import (
    body_has_reasoning_fields,
    normalize_mistral_completion,
    normalize_mistral_sse_line,
    sanitize_mistral_chat_body,
    strip_reasoning_fields,
    supports_reasoning,
)


def mistral_should_fallback(
    status_code: int,
    error_text: str,
) -> bool | None:
    """PS: stop pool rotate on permanent / org-wide Mistral errors.

    Labs-not-enabled, 422, and rate_limited fail the same across a
    farm (or burn thousands of keys). None = global default.
    """
    lower = (error_text or "").lower()
    if (
        "labs_not_enabled" in lower
        or "is a labs model" in lower
        or "labs model" in lower
    ):
        return False
    if status_code == 422:
        return False
    if status_code == 403 and (
        "labs" in lower or "not enabled" in lower
    ):
        return False
    # 429 / rate_limited: do not rotate the whole farm.
    if status_code == 429 or "rate_limited" in lower or (
        "rate limit" in lower
    ):
        return False
    return None


def mistral_reasoning_param_rejected(
    status_code: int,
    error_text: str,
) -> bool:
    """True when upstream rejected reasoning_* knobs on this model."""
    if status_code == 422:
        # Body validation — may or may not be reasoning; caller gates.
        return True
    if status_code != 400:
        return False
    lower = (error_text or "").lower()
    if "3051" in lower:
        return True
    if "reasoning_effort is not enabled" in lower:
        return True
    if "reasoning is not enabled" in lower:
        return True
    if "reasoning_effort" in lower and "not enabled" in lower:
        return True
    return False


def mistral_rewrite_body_after_error(
    status_code: int,
    error_text: str,
    model: str,
    body: dict,
) -> dict | None:
    """Strip reasoning knobs and retry same connection once.

    Mistral often returns **400** code 3051 ("reasoning_effort is not
    enabled") — not only 422. Upstream reject wins over the capability
    cache (cache can be stale or mean something else). Does **not**
    disable reasoning for models that accept it; those never hit 3051.
    """
    if not isinstance(body, dict):
        return None
    if not body_has_reasoning_fields(body):
        return None
    if not mistral_reasoning_param_rejected(status_code, error_text):
        return None
    # Explicit 400/3051: strip even if cache said True.
    if status_code == 400:
        from app.providers.mistral.models import remember_reasoning

        remember_reasoning(model, False)
        return strip_reasoning_fields(body)
    # 422: only strip when we do not know the model accepts reasoning.
    if supports_reasoning(model) is True:
        return None
    return strip_reasoning_fields(body)


class MistralHandler(BaseProviderHandler):
    """OpenAI-compatible chat with a sanitized request body."""

    # Magistral streams list-shaped content; rewrite SSE line-by-line.
    SSE_LINE_TRANSFORM = True

    async def fetch_models(
        self, api_key: str, data: dict | None = None,
    ) -> list[dict]:
        """Fetch /models and cache capabilities.reasoning."""
        del data
        if not api_key:
            raise ValueError("No API key configured")
        models_raw = await mistral_fetch_models(api_key)
        return [
            self._normalize_model(m)
            for m in models_raw
            if self._normalize_model(m).get("id")
        ]

    async def build_request_body(
        self,
        model: str,
        body: dict,
        conn_data: dict | None = None,
    ) -> tuple[bytes, dict[str, str] | None]:
        del conn_data
        sanitized = sanitize_mistral_chat_body(model, body)
        return json.dumps(sanitized).encode(), None

    def should_fallback_on_error(
        self,
        status_code: int,
        error_text: str,
    ) -> bool | None:
        return mistral_should_fallback(status_code, error_text)

    def rewrite_body_after_error(
        self,
        status_code: int,
        error_text: str,
        model: str,
        body: dict,
    ) -> dict | None:
        return mistral_rewrite_body_after_error(
            status_code, error_text, model, body,
        )

    def unwrap_response(self, response_text: str) -> dict:
        """Parse JSON and flatten Magistral thinking/text parts."""
        data = json.loads(response_text)
        if isinstance(data, dict):
            return normalize_mistral_completion(data)
        return data

    def transform_openai_sse_line(self, line: str) -> str | None:
        """Flatten list content; drop thinking-only deltas."""
        return normalize_mistral_sse_line(line)
