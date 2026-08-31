"""Provider catalog models — one list per provider id."""

from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_model import ProviderModel
from app.models.settings import KV
from app.providers.provider import Provider
from app.routers.providers.constants import normalize_models_list

_HISTORY_SCOPE = "catalog-enabled"


def resolve_enabled_flag(
    model_id: str,
    existing: dict[str, bool],
    history: dict[str, bool],
) -> bool:
    """DB row, else last known flag, else disabled (no history)."""
    if model_id in existing:
        return bool(existing[model_id])
    if model_id in history:
        return bool(history[model_id])
    return False


def parse_history_entry(raw: object) -> tuple[bool, bool]:
    """Return (enabled, custom) from a KV value."""
    if isinstance(raw, dict):
        return bool(raw.get("enabled")), bool(raw.get("custom"))
    return bool(raw), False


def prune_history(
    history: dict[str, dict[str, bool]],
    fetch_ids: set[str],
    custom_ids: set[str],
) -> dict[str, dict[str, bool]]:
    """Drop KV ids that are neither in last fetch nor custom."""
    keep = fetch_ids | custom_ids
    return {mid: flags for mid, flags in history.items() if mid in keep}


def uses_model_catalog_table(provider: str) -> bool:
    """True when this provider stores models in provider_models."""
    try:
        return bool(Provider(provider).config().MODEL_CATALOG_TABLE)
    except (ValueError, ModuleNotFoundError, AttributeError):
        return False


def _as_dict(m: ProviderModel) -> dict:
    out: dict = {"id": m.model_id, "type": m.type or "llm"}
    if m.name:
        out["name"] = m.name
    if m.custom:
        out["custom"] = True
    return out


async def list_provider_models(
    db: AsyncSession,
    provider: str,
) -> list[dict]:
    result = await db.execute(
        select(ProviderModel)
        .where(ProviderModel.provider == provider)
        .order_by(ProviderModel.model_id)
    )
    return [_as_dict(row) for row in result.scalars().all()]


async def list_enabled_ids(
    db: AsyncSession,
    provider: str,
) -> set[str]:
    result = await db.execute(
        select(ProviderModel.model_id).where(
            ProviderModel.provider == provider,
            ProviderModel.enabled.is_(True),
        )
    )
    return set(result.scalars().all())


async def list_disabled_ids(
    db: AsyncSession,
    provider: str,
) -> list[str]:
    result = await db.execute(
        select(ProviderModel.model_id).where(
            ProviderModel.provider == provider,
            ProviderModel.enabled.is_(False),
        )
    )
    return list(result.scalars().all())


async def catalog_initialized(
    db: AsyncSession,
    provider: str,
) -> bool:
    result = await db.execute(
        select(ProviderModel.id)
        .where(ProviderModel.provider == provider)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _load_enabled_history(
    db: AsyncSession,
    provider: str,
) -> dict[str, dict[str, bool]]:
    result = await db.execute(
        select(KV).where(
            KV.scope == _HISTORY_SCOPE,
            KV.key == provider,
        )
    )
    row = result.scalar_one_or_none()
    if row is None or not row.value:
        return {}
    try:
        raw = json.loads(row.value)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, bool]] = {}
    for mid, flag in raw.items():
        enabled, custom = parse_history_entry(flag)
        out[str(mid)] = {"enabled": enabled, "custom": custom}
    return out


async def _save_enabled_history(
    db: AsyncSession,
    provider: str,
    flags: dict[str, bool],
) -> None:
    payload = json.dumps(flags)
    result = await db.execute(
        select(KV).where(
            KV.scope == _HISTORY_SCOPE,
            KV.key == provider,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(KV(
            scope=_HISTORY_SCOPE,
            key=provider,
            value=payload,
        ))
    else:
        row.value = payload
    await db.flush()


async def _merge_enabled_history(
    db: AsyncSession,
    provider: str,
    flags: dict[str, dict[str, bool]],
) -> None:
    if not flags:
        return
    history = await _load_enabled_history(db, provider)
    for mid, entry in flags.items():
        prev = history.get(mid, {"enabled": False, "custom": False})
        history[mid] = {
            "enabled": bool(entry.get("enabled", prev["enabled"])),
            "custom": bool(entry.get("custom", prev["custom"])),
        }
    await _save_enabled_history(db, provider, history)


async def replace_provider_models(
    db: AsyncSession,
    provider: str,
    models: list,
    *,
    force_enable: bool = False,
) -> list[dict]:
    """Replace fetched catalog rows. Custom rows stay. KV is pruned."""
    normalized = normalize_models_list(models or [])
    existing: dict[str, bool] = {}
    history_enabled: dict[str, bool] = {}
    custom_keep: dict[str, dict] = {}
    history = await _load_enabled_history(db, provider)
    result = await db.execute(
        select(ProviderModel).where(
            ProviderModel.provider == provider,
        )
    )
    for row in result.scalars().all():
        existing[row.model_id] = row.enabled
        if row.custom:
            custom_keep[row.model_id] = {
                "enabled": row.enabled,
                "type": row.type or "llm",
                "name": row.name,
            }
    for mid, entry in history.items():
        history_enabled[mid] = bool(entry.get("enabled"))
        if entry.get("custom") and mid not in custom_keep:
            custom_keep[mid] = {
                "enabled": bool(entry.get("enabled")),
                "type": "llm",
                "name": None,
            }

    await db.execute(
        delete(ProviderModel).where(
            ProviderModel.provider == provider,
        )
    )
    kept: list[dict] = []
    seen: set[str] = set()
    kv: dict[str, dict[str, bool]] = {}
    for item in normalized:
        mid = str(item.get("id") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        if force_enable:
            enabled = True
        else:
            enabled = resolve_enabled_flag(
                mid, existing, history_enabled,
            )
        kv[mid] = {"enabled": enabled, "custom": False}
        db.add(ProviderModel(
            provider=provider,
            model_id=mid,
            type=item.get("type") or "llm",
            name=item.get("name"),
            enabled=enabled,
            custom=False,
        ))
        kept.append(item)
        custom_keep.pop(mid, None)
    for mid, meta in custom_keep.items():
        enabled = bool(meta["enabled"])
        kv[mid] = {"enabled": enabled, "custom": True}
        db.add(ProviderModel(
            provider=provider,
            model_id=mid,
            type=meta.get("type") or "llm",
            name=meta.get("name"),
            enabled=enabled,
            custom=True,
        ))
        kept.append({
            "id": mid,
            "type": meta.get("type") or "llm",
            "custom": True,
        })
    await db.flush()
    await _save_enabled_history(db, provider, kv)
    return kept


async def clear_provider_models(
    db: AsyncSession,
    provider: str,
) -> int:
    result = await db.execute(
        select(ProviderModel).where(
            ProviderModel.provider == provider,
        )
    )
    flags: dict[str, dict[str, bool]] = {}
    for row in result.scalars().all():
        flags[row.model_id] = {
            "enabled": bool(row.enabled),
            "custom": bool(row.custom),
        }
    await _merge_enabled_history(db, provider, flags)
    deleted = await db.execute(
        delete(ProviderModel).where(
            ProviderModel.provider == provider,
        )
    )
    await db.flush()
    return int(deleted.rowcount or 0)


async def upsert_custom_model(
    db: AsyncSession,
    provider: str,
    model_id: str,
    *,
    enabled: bool = True,
    model_type: str = "llm",
    name: str | None = None,
) -> dict:
    """Add or keep a user-added catalog model."""
    mid = (model_id or "").strip()
    if not mid:
        raise ValueError("model id required")
    result = await db.execute(
        select(ProviderModel).where(
            ProviderModel.provider == provider,
            ProviderModel.model_id == mid,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ProviderModel(
            provider=provider,
            model_id=mid,
            type=model_type,
            name=name,
            enabled=enabled,
            custom=True,
        )
        db.add(row)
    else:
        row.custom = True
        row.enabled = enabled
        if name:
            row.name = name
    await db.flush()
    await _merge_enabled_history(db, provider, {
        mid: {"enabled": row.enabled, "custom": True},
    })
    return _as_dict(row)


async def set_models_enabled(
    db: AsyncSession,
    provider: str,
    model_ids: list[str],
    enabled: bool,
) -> None:
    if not model_ids:
        return
    result = await db.execute(
        select(ProviderModel).where(
            ProviderModel.provider == provider,
            ProviderModel.model_id.in_(model_ids),
        )
    )
    found = {row.model_id: row for row in result.scalars().all()}
    changed: dict[str, dict[str, bool]] = {}
    for mid in model_ids:
        row = found.get(mid)
        if row is None:
            continue
        row.enabled = enabled
        changed[mid] = {
            "enabled": enabled,
            "custom": bool(row.custom),
        }
    await db.flush()
    await _merge_enabled_history(db, provider, changed)


async def enable_all_models(
    db: AsyncSession,
    provider: str,
) -> None:
    result = await db.execute(
        select(ProviderModel).where(
            ProviderModel.provider == provider,
        )
    )
    flags: dict[str, dict[str, bool]] = {}
    for row in result.scalars().all():
        row.enabled = True
        flags[row.model_id] = {
            "enabled": True,
            "custom": bool(row.custom),
        }
    await db.flush()
    await _merge_enabled_history(db, provider, flags)
