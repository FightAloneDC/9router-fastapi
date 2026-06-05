"""Provider model fetching and clearing endpoints."""

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.models.settings import SettingsModel
from app.providers.base import BaseProviderConfig
from app.providers.model_helpers import fetch_models_header_auth
from app.providers.provider import Provider
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.constants import PROVIDER_DEFAULTS, normalize_models_list
from app.routers.providers.helpers import _normalize_model, _parse_openai_models


# ── Node-based model fetching ─────────────────────────────────────────────

async def _fetch_node_models(node: ProviderNode, api_key: str) -> list[dict]:
    """Fetch models from a custom compatible node (openai/anthropic)."""
    node_data: dict = json.loads(node.data) if node.data else {}
    node_base_url: str = node_data.get("baseUrl", "")

    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")
    if not node_base_url:
        raise HTTPException(status_code=400, detail="No base URL configured")

    if node.type == "anthropic-compatible":
        normalized: str = node_base_url.rstrip("/")
        if normalized.endswith("/messages"):
            normalized = normalized[:-9]
        config = BaseProviderConfig(
            PROVIDER_NAME=node.name or node.id,
            PROVIDER_ID=node.id,
            ALIAS=node.id,
            BASE_URL=normalized,
            AUTH_HEADER="x-api-key",
            AUTH_PREFIX="",
            EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
        )
    else:
        config = BaseProviderConfig(
            PROVIDER_NAME=node.name or node.id,
            PROVIDER_ID=node.id,
            ALIAS=node.id,
            BASE_URL=node_base_url,
        )

    try:
        models_raw: list[dict] = await fetch_models_header_auth(config, api_key)
        models: list[dict] = [_normalize_model(m) for m in models_raw if _normalize_model(m).get("id")]
        return models
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to {node_base_url}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection timed out")


# ── Built-in provider model fetching ──────────────────────────────────────

async def _fetch_builtin_models(
    provider: str, api_key: str, data: dict,
) -> list[dict]:
    """Fetch models from a built-in provider using the Provider class."""
    # Qoder has special COSY-signed handling
    if provider == "qoder":
        return await _fetch_qoder_models(api_key, data)

    try:
        p: Provider = Provider(provider)
    except (ValueError, ModuleNotFoundError):
        # Provider not in new system — fallback to PROVIDER_DEFAULTS
        return await _fetch_fallback(provider, api_key)

    token: str = data.get("accessToken") or api_key
    if not token:
        raise HTTPException(status_code=401, detail="No valid token found")

    # Pass region for region-aware providers
    psd: dict = data.get("providerSpecificData", {})
    region: str = psd.get("region", "")

    try:
        if region:
            models_raw: list[dict] = await p.fetch_models(token, region=region)
        else:
            models_raw: list[dict] = await p.fetch_models(token)
        models: list[dict] = [_normalize_model(m) for m in models_raw if _normalize_model(m).get("id")]
        return models
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to {p.base_url()}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch models: {e.response.status_code}")


async def _fetch_fallback(provider: str, api_key: str) -> list[dict]:
    """Fallback for providers not yet migrated to Provider class."""
    default_url: str = PROVIDER_DEFAULTS.get(provider, {}).get("baseUrl", "")
    if not default_url or not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider} does not support model fetching",
        )
    config = BaseProviderConfig(
        PROVIDER_NAME=provider,
        PROVIDER_ID=provider,
        ALIAS=provider,
        BASE_URL=default_url,
    )
    try:
        models_raw: list[dict] = await fetch_models_header_auth(config, api_key)
        models: list[dict] = [_normalize_model(m) for m in models_raw if _normalize_model(m).get("id")]
        return models
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to {default_url}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection timed out")


async def _fetch_qoder_models(api_key: str, data: dict) -> list[dict]:
    """Qoder has COSY-signed model fetching — keep as special case."""
    from app.services.qoder.models import resolve_qoder_models

    credentials: dict = {
        "access_token": data.get("accessToken", ""),
        "email": data.get("email", ""),
        "display_name": data.get("name", ""),
        "provider_specific": {
            "userId": data.get("userId", ""),
            "machineId": data.get("machineId", ""),
        },
    }
    result: dict = await resolve_qoder_models(credentials, force_refresh=True)
    models: list[dict] = []
    for m in result.get("models", []):
        models.append({
            "id": f"qoder/{m.get('id')}",
            "name": m.get("name", m.get("id")),
            "type": "llm",
            "contextLength": m.get("context_length", 0),
        })
    return [_normalize_model(m) for m in models if _normalize_model(m).get("id")]


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/providers/{conn_id}/models")
async def fetch_provider_models(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """Fetch available models from a provider's API using the connection's credentials."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn: ProviderConnection | None = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    data: dict = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key: str = data.get("apiKey", "")
    provider: str = conn.provider

    # Check if this is a compatible provider (node-based)
    node_result = await db.execute(
        select(ProviderNode).where(ProviderNode.id == provider)
    )
    node: ProviderNode | None = node_result.scalar_one_or_none()

    if node:
        models: list[dict] = await _fetch_node_models(node, api_key)
    else:
        models = await _fetch_builtin_models(provider, api_key, data)

    # Persist and return
    data["models"] = [
        {"id": m.get("id"), "type": m.get("type", "llm")}
        for m in models if m.get("id")
    ]
    conn.data = json.dumps(data)
    await db.flush()
    return {
        "provider": provider,
        "connectionId": str(conn.id),
        "models": models,
    }


@router.delete("/providers/{conn_id}/models")
async def clear_provider_models(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """Clear all stored models from a provider connection and remove disabled models."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn: ProviderConnection | None = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    data: dict = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    current_models: list = data.get("models", [])
    cleared_count: int = len(current_models) if isinstance(current_models, list) else 0

    data["models"] = []
    conn.data = json.dumps(data)

    # Also clear disabled models for this provider alias from settings
    provider_alias: str = conn.provider
    settings_result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    settings_row = settings_result.scalar_one_or_none()
    if settings_row:
        try:
            settings_data: dict = json.loads(settings_row.data) if settings_row.data else {}
        except (json.JSONDecodeError, TypeError):
            settings_data = {}
        disabled: dict = settings_data.get("disabledModels", {})
        if provider_alias in disabled:
            del disabled[provider_alias]
            settings_data["disabledModels"] = disabled
            settings_row.data = json.dumps(settings_data)

    await db.flush()
    return {"ok": True, "clearedCount": cleared_count}


@router.patch("/providers/{conn_id}/models/type")
async def change_model_type(
    conn_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """Override the type for a specific model in a provider connection."""
    VALID_TYPES: set[str] = {
        "llm", "embedding", "tts", "stt", "image", "imageToText",
        "video", "music", "webSearch", "webFetch",
    }

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn: ProviderConnection | None = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    model_id: str | None = body.get("model_id")
    new_type: str | None = body.get("type")
    if not model_id or not new_type:
        raise HTTPException(status_code=400, detail="model_id and type are required")
    if new_type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{new_type}'. Valid: {', '.join(sorted(VALID_TYPES))}",
        )

    data: dict = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    models: list = data.get("models", [])
    normalized: list[dict] = normalize_models_list(models)

    found: bool = False
    for m in normalized:
        if isinstance(m, dict) and m.get("id") == model_id:
            m["type"] = new_type
            found = True
            break

    if not found:
        normalized.append({"id": model_id, "type": new_type})

    data["models"] = normalized
    data.pop("modelTypes", None)
    conn.data = json.dumps(data)
    await db.flush()

    return {"ok": True, "model_id": model_id, "type": new_type}
