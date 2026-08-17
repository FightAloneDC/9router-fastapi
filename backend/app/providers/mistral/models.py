"""Mistral model fetching — cache capabilities.reasoning from upstream."""

from __future__ import annotations

from app.providers.mistral.config import MistralConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: MistralConfig = MistralConfig()

# model_id → capabilities.reasoning (from last successful /models).
_REASONING_BY_ID: dict[str, bool] = {}


def clear_reasoning_cache() -> None:
    """Test helper — empty the in-process capability cache."""
    _REASONING_BY_ID.clear()


def remember_reasoning(model_id: str, supported: bool) -> None:
    """Record upstream capabilities.reasoning for *model_id*."""
    mid = (model_id or "").strip()
    if not mid:
        return
    _REASONING_BY_ID[mid] = bool(supported)


def reasoning_capability(model_id: str) -> bool | None:
    """True/False from cache; None if this process has not fetched yet."""
    mid = (model_id or "").strip()
    if not mid:
        return None
    if mid in _REASONING_BY_ID:
        return _REASONING_BY_ID[mid]
    # Upstream id may be bare; client may send provider/id.
    if "/" in mid:
        bare = mid.rsplit("/", 1)[-1]
        if bare in _REASONING_BY_ID:
            return _REASONING_BY_ID[bare]
    return None


def parse_response(data: dict) -> list[dict]:
    """Extract models and remember capabilities.reasoning."""
    rows = data.get("data", [])
    if not isinstance(rows, list):
        return []
    out: list[dict] = []
    for m in rows:
        if not isinstance(m, dict):
            continue
        mid = m.get("id") or ""
        caps = m.get("capabilities")
        if mid and isinstance(caps, dict):
            remember_reasoning(mid, bool(caps.get("reasoning")))
        out.append(m)
    return out


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Mistral."""
    return await fetch_models_header_auth(
        _config, api_key, parse_fn=parse_response,
    )
