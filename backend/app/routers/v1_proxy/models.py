"""GET /v1/models, /v1/models/info, /v1/models/{kind} — Model listing endpoints."""

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.services.api_key_auth import validate_api_key
from app.models.provider import ProviderConnection
from app.models.combo import Combo
from app.models.settings import SettingsModel
from app.services.proxy import ID_TO_ALIAS
from app.routers.providers.constants import MODEL_TYPE_OVERRIDES, infer_model_type

router = APIRouter()

_VALID_MODEL_KINDS: set[str] = {"llm", "embedding", "tts", "stt", "image", "imageToText", "webSearch", "webFetch"}


async def _get_disabled_models(db: AsyncSession) -> dict[str, list[str]]:
    """Load disabled models map from global settings."""
    settings_result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    settings_row = settings_result.scalar_one_or_none()
    if settings_row and settings_row.data:
        try:
            settings_data: dict = json.loads(settings_row.data)
            return settings_data.get("disabledModels", {})
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


@router.get("/models")
async def list_models(
    kind: str | None = Query(None, description="Filter by model type (e.g. llm, embedding, tts, stt, image)"),
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> dict:
    """List available models (OpenAI-compatible /v1/models endpoint).

    When `kind` is provided, only return models whose resolved type matches.
    Combos are always type "llm". Provider models use: user override > static > regex > llm.
    """
    models: list[dict] = []
    seen_model_ids: set[str] = set()

    disabled_models: dict[str, list[str]] = await _get_disabled_models(db)

    # Add combos as models (combos are always type "llm")
    if kind is None or kind == "llm":
        result = await db.execute(select(Combo))
        combos = result.scalars().all()
        for combo in combos:
            model_id: str = combo.name
            if model_id not in seen_model_ids:
                models.append({
                    "id": model_id,
                    "object": "model",
                    "created": int(combo.created_at.timestamp()) if combo.created_at else 0,
                    "owned_by": "9router",
                })
                seen_model_ids.add(model_id)

    # Add provider-specific models from connections
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.is_active == True)
    )
    connections = result.scalars().all()

    for conn in connections:
        data: dict = json.loads(conn.data) if conn.data else {}
        conn_models: list = data.get("models", [])

        if not conn_models:
            continue

        provider_alias: str = ID_TO_ALIAS.get(conn.provider, conn.provider)
        disabled_for_provider: set[str] = set(disabled_models.get(provider_alias, []))

        for m in conn_models:
            model_id = m if isinstance(m, str) else m.get("id", "")
            if not model_id:
                continue

            # Resolve model type: user override > static > regex > default llm
            model_type: str = "llm"
            model_types_override: dict = data.get("modelTypes", {})
            if model_id in model_types_override:
                model_type = model_types_override[model_id]
            elif isinstance(m, dict) and "type" in m:
                model_type = m["type"]
            elif model_id in MODEL_TYPE_OVERRIDES:
                model_type = MODEL_TYPE_OVERRIDES[model_id]
            else:
                model_type = infer_model_type(model_id)

            if kind is not None and model_type != kind:
                continue

            full_model_id: str = f"{provider_alias}/{model_id}"

            if model_id in disabled_for_provider or full_model_id in seen_model_ids:
                continue

            models.append({
                "id": full_model_id,
                "object": "model",
                "created": int(conn.created_at.timestamp()) if conn.created_at else 0,
                "owned_by": provider_alias,
            })
            seen_model_ids.add(full_model_id)

    return {
        "object": "list",
        "data": models,
    }


@router.get("/models/info")
async def models_info(
    id: str = Query(..., description="Comma-separated model IDs to look up"),
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> dict:
    """Get metadata for specific models by ID.

    Accepts comma-separated model IDs and returns matching models
    with their type and ownership information. Used by CLI tools
    and external clients that need model metadata.
    """
    requested_ids: set[str] = {mid.strip() for mid in id.split(",") if mid.strip()}
    if not requested_ids:
        return {"object": "list", "data": []}

    disabled_models: dict[str, list[str]] = await _get_disabled_models(db)

    result_data: list[dict] = []
    found_ids: set[str] = set()

    # Check combos
    combo_result = await db.execute(select(Combo))
    for combo in combo_result.scalars().all():
        if combo.name in requested_ids and combo.name not in found_ids:
            result_data.append({
                "id": combo.name,
                "object": "model",
                "created": int(combo.created_at.timestamp()) if combo.created_at else 0,
                "owned_by": "9router",
                "type": "llm",
            })
            found_ids.add(combo.name)

    # Check provider models
    conn_result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.is_active == True)
    )
    for conn in conn_result.scalars().all():
        data: dict = json.loads(conn.data) if conn.data else {}
        conn_models: list = data.get("models", [])

        if not conn_models:
            continue

        provider_alias: str = ID_TO_ALIAS.get(conn.provider, conn.provider)
        disabled_for_provider: set[str] = set(disabled_models.get(provider_alias, []))
        model_types_override: dict = data.get("modelTypes", {})

        for m in conn_models:
            model_id: str = m if isinstance(m, str) else m.get("id", "")
            if not model_id:
                continue

            full_model_id: str = f"{provider_alias}/{model_id}"
            if full_model_id not in requested_ids or full_model_id in found_ids:
                continue
            if model_id in disabled_for_provider:
                continue

            model_type: str = "llm"
            if model_id in model_types_override:
                model_type = model_types_override[model_id]
            elif isinstance(m, dict) and "type" in m:
                model_type = m["type"]
            elif model_id in MODEL_TYPE_OVERRIDES:
                model_type = MODEL_TYPE_OVERRIDES[model_id]
            else:
                model_type = infer_model_type(model_id)

            result_data.append({
                "id": full_model_id,
                "object": "model",
                "created": int(conn.created_at.timestamp()) if conn.created_at else 0,
                "owned_by": provider_alias,
                "type": model_type,
            })
            found_ids.add(full_model_id)

    return {"object": "list", "data": result_data}


@router.get("/models/{kind}")
async def list_models_by_kind(
    kind: str,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> dict:
    """List models filtered by kind via path parameter.

    This is a convenience alias for ``GET /v1/models?kind={kind}``
    for CLI tools and external clients that prefer path-based filtering.
    Only matches known model kinds; other values fall through to get_model.
    """
    if kind not in _VALID_MODEL_KINDS:
        return await get_model(model_path=kind, db=db, api_key_info=api_key_info)
    return await list_models(kind=kind, db=db, api_key_info=api_key_info)


@router.get("/models/{model_path:path}")
async def get_model(
    model_path: str,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> dict:
    """Get a specific model (OpenAI-compatible)."""
    return {
        "id": model_path,
        "object": "model",
        "created": 0,
        "owned_by": "9router",
    }
