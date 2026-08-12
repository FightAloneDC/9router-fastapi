"""Qoder model catalog fetcher.

⚠️  CRITICAL: Do NOT modify this provider without user approval.
    Extensive investigation and trial-error has been done.
    See docs/qoder/BUG-FIXING-LOG.md before making any changes.

Calls /algo/api/v2/model/list (COSY-signed) on the inference host to get
the live catalog for an authenticated Qoder account, then caches the
per-model `model_config` blocks by key.

On any error the live cache stays empty and chat requests surface the
problem to the user as "model config not yet fetched, retry shortly".
"""

def parse_response(data: dict) -> list[dict]:
    """Extract models list from Qoder API response.

    Qoder doesn't use this — models are fetched via handler.fetch_models().
    This is a stub to satisfy the Provider class interface.
    """
    return []

import hashlib
import time
from typing import Any

import httpx

from .constants import QODER_MODEL_LIST_URL
from .cosy import build_cosy_headers
from app.services.outbound_proxy import create_upstream_client

# Cache TTL: 1 hour
CACHE_TTL_MS = 60 * 60 * 1000

# In-memory cache: { cache_key: { expires_at, models, raw_configs, fetched } }
_catalog_cache: dict[str, dict[str, Any]] = {}


def _cache_key(user_id: str, access_token: str) -> str:
    """Stable cache key per credential."""
    seed = user_id or access_token or "anonymous"
    return hashlib.sha256(f"qoder:{seed}".encode()).hexdigest()


def _cosy_creds_from_connection(credentials: dict[str, Any]) -> dict[str, str]:
    """Extract COSY credentials from connection data."""
    psd = credentials.get("provider_specific", {})
    # Qoder returns 'id' not 'userId' - check both
    user_id = psd.get("userId") or psd.get("id") or credentials.get("user_id", "")
    return {
        "user_id": user_id,
        "auth_token": credentials.get("access_token", ""),
        "name": credentials.get("display_name", ""),
        "email": credentials.get("email", ""),
        "machine_id": psd.get("machineId", ""),
    }


async def fetch_qoder_catalog(
    credentials: dict[str, Any],
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Fetch the live model list for this credential.

    Returns:
        Dict with 'models' list and 'raw_configs' map, or None on error

    Raises:
        httpx.HTTPStatusError: If the API returns a non-200 status code (e.g. 403 for expired token)
    """
    creds = _cosy_creds_from_connection(credentials)
    if not creds["user_id"] or not creds["auth_token"]:
        return None

    headers = build_cosy_headers(
        body=b"",
        request_url=QODER_MODEL_LIST_URL,
        user_id=creds["user_id"],
        auth_token=creds["auth_token"],
        name=creds["name"],
        email=creds["email"],
        machine_id=creds["machine_id"],
    )

    async with create_upstream_client(timeout=timeout) as client:
        response = await client.get(QODER_MODEL_LIST_URL, headers=headers)

    if response.status_code != 200:
        # Parse error message from Qoder API
        try:
            error_body = response.json()
            error_message = error_body.get("message", error_body.get("errorMessage", f"HTTP {response.status_code}"))
        except Exception:
            error_message = f"HTTP {response.status_code}: {response.text[:200]}"
        raise httpx.HTTPStatusError(
            message=f"Qoder model list failed: {error_message}",
            request=response.request,
            response=response,
        )

    body = response.json()
    if not isinstance(body.get("chat"), list):
        return None

    models = []
    raw_configs = {}
    for entry in body["chat"]:
        # Qoder uses 'key' not 'modelId' or 'id'
        model_id = entry.get("key") or entry.get("modelId") or entry.get("id")
        if not model_id:
            continue

        model_info = {
            "id": model_id,
            "name": entry.get("display_name") or entry.get("name", model_id),
            "context_length": entry.get("max_input_tokens") or entry.get("contextLength", 0),
            "is_vl": entry.get("isVL") or entry.get("is_vl", False),
            "is_reasoning": entry.get("isReasoning") or entry.get("is_reasoning", False),
            "max_output_tokens": entry.get("maxOutputTokens") or entry.get("max_output_tokens", 0),
            "description": entry.get("description", ""),
            "format": entry.get("format", ""),
            "source": entry.get("source", ""),
            "price_factor": entry.get("price_factor", 1.0),
        }
        models.append(model_info)

        # Store the full config for chat requests (Node.js uses the entire entry)
        raw_configs[model_id] = entry

    return {"models": models, "raw_configs": raw_configs}


async def resolve_qoder_models(
    credentials: dict[str, Any],
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Resolve Qoder models, using cache if available.

    Args:
        credentials: Connection credentials dict
        force_refresh: Force refresh from API

    Returns:
        Dict with 'models' list

    Raises:
        httpx.HTTPStatusError: If the API returns a non-200 status code (e.g. 403 for expired token)
    """
    psd = credentials.get("provider_specific", {})
    user_id = psd.get("userId") or credentials.get("user_id", "")
    access_token = credentials.get("access_token", "")

    key = _cache_key(user_id, access_token)
    now_ms = int(time.time() * 1000)

    # Check cache
    if not force_refresh and key in _catalog_cache:
        cached = _catalog_cache[key]
        if cached.get("expires_at", 0) > now_ms and cached.get("fetched"):
            return {"models": cached["models"]}

    # Fetch from API — may raise httpx.HTTPStatusError
    result = await fetch_qoder_catalog(credentials)
    if result and result["models"]:
        _catalog_cache[key] = {
            "expires_at": now_ms + CACHE_TTL_MS,
            "models": result["models"],
            "raw_configs": result["raw_configs"],
            "fetched": True,
        }
        return {"models": result["models"]}

    # Return cached if available, even if expired
    if key in _catalog_cache:
        return {"models": _catalog_cache[key].get("models", [])}

    return {"models": []}


def get_qoder_model_config(user_id: str, access_token: str, model_id: str) -> dict[str, Any] | None:
    """Get the raw model config for a specific model.

    Args:
        user_id: Qoder user ID
        access_token: Access token
        model_id: Model identifier

    Returns:
        Model config dict or None
    """
    key = _cache_key(user_id, access_token)
    cached = _catalog_cache.get(key)
    if not cached:
        return None

    raw_configs = cached.get("raw_configs", {})
    return raw_configs.get(model_id)
