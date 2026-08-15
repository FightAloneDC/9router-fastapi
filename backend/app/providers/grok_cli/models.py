"""Grok CLI model fetching and parsing.

Port of ``open-sse/services/grokCliModels.js`` from the Next.js reference.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.grok_cli.constants import (
    GROK_CLI_BASE_URL,
    GROK_CLI_CLIENT_IDENTIFIER,
    GROK_CLI_DROP_MODEL_IDS,
    GROK_CLI_MODEL,
    GROK_CLI_TOKEN_AUTH,
    GROK_CLI_USER_AGENT,
    GROK_CLI_VERSION,
)
from app.services.outbound_proxy import create_upstream_client

_MODELS_URL = f"{GROK_CLI_BASE_URL}/models"


def _model_entries(data: Any) -> list[tuple[str | None, Any]]:
    """Extract the model list from the raw /models response."""
    if isinstance(data, list):
        value: Any = data
    elif isinstance(data, dict):
        value = data.get("data", data.get("models", data.get("results", [])))
    else:
        value = []
    if isinstance(value, list):
        return [(None, item) for item in value]
    if isinstance(value, dict):
        return list(value.items())
    return []


def parse_response(data: Any) -> list[dict]:
    """Parse the raw /models payload into normalized model dicts."""
    seen: set[str] = set()
    models: list[dict] = []

    for key, raw in _model_entries(data):
        item = {"id": raw} if isinstance(raw, str) else raw
        if not isinstance(item, dict):
            continue
        model_id = str(
            item.get("id")
            or item.get("model_id")
            or item.get("modelId")
            or item.get("model")
            or item.get("slug")
            or key
            or item.get("name")
            or ""
        ).strip()
        if (
            not model_id
            or model_id in seen
            or model_id in GROK_CLI_DROP_MODEL_IDS
        ):
            continue
        seen.add(model_id)

        model: dict[str, Any] = {
            "id": model_id,
            "name": (
                item.get("display_name")
                or item.get("displayName")
                or item.get("name")
                or model_id
            ),
        }
        context_length = _to_positive_int(
            item.get("context_length")
            or item.get("contextLength")
            or item.get("context_window")
            or item.get("contextWindow")
        )
        max_output = _to_positive_int(
            item.get("max_output_tokens") or item.get("maxOutputTokens")
        )
        if context_length:
            model["contextLength"] = context_length
        if max_output:
            model["maxOutputTokens"] = max_output
        if model_id == GROK_CLI_MODEL:
            model.setdefault("contextLength", 500000)
            model.setdefault("maxOutputTokens", 64000)
        models.append(model)

    return models


def _to_positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def build_models_headers(
    access_token: str, provider_specific: dict | None = None,
) -> dict[str, str]:
    """Headers for /models and /user endpoints (official CLI fingerprint)."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": GROK_CLI_USER_AGENT,
        "x-xai-token-auth": GROK_CLI_TOKEN_AUTH,
        "x-grok-client-version": GROK_CLI_VERSION,
        "x-grok-client-identifier": GROK_CLI_CLIENT_IDENTIFIER,
        "x-grok-client-mode": "headless",
    }
    psd = provider_specific or {}
    email = psd.get("email")
    user_id = psd.get("userId") or psd.get("principalId")
    if email:
        headers["x-email"] = email
    if user_id:
        headers["x-userid"] = str(user_id)
    return headers


async def fetch_models(
    api_key: str, data: dict | None = None,
) -> list[dict]:
    """Fetch models from cli-chat-proxy.grok.com.

    Raises:
        httpx.HTTPStatusError: on non-2xx (e.g. 401 expired token).
    """
    if not api_key:
        raise ValueError("No Grok CLI access token configured")
    psd = (data or {}).get("providerSpecificData") or {}
    headers = build_models_headers(api_key, psd)

    async with create_upstream_client(timeout=30.0) as client:
        resp = await client.get(_MODELS_URL, headers=headers)
        resp.raise_for_status()
        return parse_response(resp.json())
