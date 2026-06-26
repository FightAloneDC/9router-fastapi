"""OpenCode Free model fetching.

Fetches models from the OpenCode zen endpoint and filters to
free-tier models (IDs ending with -free, plus known free models).
"""

from __future__ import annotations

import logging

import httpx

from app.routers.providers.constants import SUGGESTED_MODELS_FILTERS

logger = logging.getLogger(__name__)

MODELS_URL: str = "https://opencode.ai/zen/v1/models"
TIMEOUT: float = 15.0


async def fetch_models(api_key: str = "") -> list[dict]:
    """Fetch free models from OpenCode zen endpoint.

    Args:
        api_key: Ignored — OpenCode Free is a noAuth provider.

    Returns:
        Filtered list of free models with {id, name} fields.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(MODELS_URL)
        resp.raise_for_status()
        raw_models: list[dict] = resp.json().get("data", [])

    model_filter = SUGGESTED_MODELS_FILTERS.get("opencode-free")
    if model_filter:
        return model_filter(raw_models)

    # Fallback: return all models if filter not found
    return [
        {"id": m.get("id"), "name": m.get("id")}
        for m in raw_models
        if m.get("id")
    ]
