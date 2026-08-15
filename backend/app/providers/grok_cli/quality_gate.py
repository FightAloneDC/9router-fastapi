"""Literal-407 quality gate for grok-cli connections.

Probe that connection only (no pool fallback). Pass = stripped
assistant text is exactly ``407``. No TTL cache.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.services.outbound_proxy import create_upstream_client

logger = logging.getLogger(__name__)

PROBE_USER = "reply exactly with : 407"
PROBE_MODEL = "grok-4.6"
PASS_TEXT = "407"
PROBE_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=25.0,
    write=15.0,
    pool=10.0,
)


def probe_passes(text: str) -> bool:
    """True iff stripped assistant text is exactly 407."""
    return (text or "").strip() == PASS_TEXT


def assistant_text_from_completed(resp: dict) -> str:
    """Extract assistant text from a Responses ``response`` object."""
    from app.providers.grok_cli.transform import (
        responses_to_openai_response,
    )

    translated = responses_to_openai_response(resp, "")
    choices = translated.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    if message.get("tool_calls"):
        return ""
    content = message.get("content") or ""
    return str(content)


def completed_from_sse(raw: str) -> dict:
    """Parse SSE text and return the last response.completed payload."""
    completed: dict = {}
    for line in raw.splitlines():
        data_str = line.strip()
        if not data_str.startswith("data:"):
            continue
        payload = data_str[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "response.completed":
            completed = event.get("response") or {}
    return completed


async def probe_literal_407(
    *,
    handler,
    url: str,
    conn_data: dict,
    proxy: str | None = None,
    connection_id: str | None = None,
) -> bool:
    """POST a plain-chat probe on this connection. No fallback."""
    probe_body = {
        "model": PROBE_MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": PROBE_USER}],
    }
    try:
        raw_body, headers = await handler.build_request_body(
            PROBE_MODEL, probe_body, conn_data,
        )
    except Exception as exc:
        logger.warning(
            "grok-cli quality-gate build failed conn=%s: %s",
            connection_id, exc,
        )
        return False

    try:
        async with create_upstream_client(
            proxy=proxy, timeout=PROBE_TIMEOUT,
        ) as client:
            async with client.stream(
                "POST", url, content=raw_body, headers=headers,
            ) as resp:
                if resp.status_code >= 400:
                    logger.warning(
                        "grok-cli quality-gate HTTP %s conn=%s",
                        resp.status_code, connection_id,
                    )
                    return False
                buffer = b""
                async for chunk in resp.aiter_bytes():
                    buffer += chunk
    except Exception as exc:
        logger.warning(
            "grok-cli quality-gate error conn=%s: %s",
            connection_id, exc,
        )
        return False

    raw = buffer.decode("utf-8", errors="ignore")
    completed = completed_from_sse(raw)
    text = assistant_text_from_completed(completed)
    passed = probe_passes(text)
    if not passed:
        preview = text.replace("\n", " ")[:80]
        logger.warning(
            "grok-cli quality-gate fail conn=%s text=%r",
            connection_id, preview,
        )
    return passed
