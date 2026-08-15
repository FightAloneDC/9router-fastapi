"""Provider prefix: DB row wins, else config.ALIAS."""

from __future__ import annotations

_overrides: dict[str, str] = {}


def set_overrides(mapping: dict[str, str]) -> None:
    """Replace in-memory DB overlay (tests + cache refresh)."""
    global _overrides
    _overrides = {
        str(k): str(v).strip()
        for k, v in mapping.items()
        if str(v).strip()
    }


async def refresh_from_db(db: object) -> None:
    """Load provider_aliases into memory. No-op if table missing."""
    from sqlalchemy import select

    from app.models.provider_alias import ProviderAlias

    try:
        result = await db.execute(select(ProviderAlias))
    except Exception:
        set_overrides({})
        return
    mapping = {
        row.provider: row.alias
        for row in result.scalars().all()
        if row.alias
    }
    set_overrides(mapping)


async def upsert_alias(
    db: object,
    provider: str,
    alias: str | None,
) -> None:
    """Set or clear a DB prefix. Empty value deletes the row."""
    from sqlalchemy import delete, select

    from app.models.provider_alias import ProviderAlias

    pid = (provider or "").strip()
    val = (alias or "").strip()
    if not pid:
        return
    if not val:
        await db.execute(
            delete(ProviderAlias).where(ProviderAlias.provider == pid),
        )
        await refresh_from_db(db)
        return
    result = await db.execute(
        select(ProviderAlias).where(ProviderAlias.provider == pid),
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(ProviderAlias(provider=pid, alias=val))
    else:
        row.alias = val
    await db.flush()
    await refresh_from_db(db)


def overlay_id_to_alias(config: dict[str, str]) -> dict[str, str]:
    """Display prefix: DB replaces config when present."""
    out = dict(config)
    out.update(_overrides)
    return out


def overlay_alias_to_id(config: dict[str, str]) -> dict[str, str]:
    """Incoming prefix = DB else config. Provider id always resolves."""
    out = dict(config)
    for provider_id, alias in _overrides.items():
        for key, pid in list(out.items()):
            if pid == provider_id and key != provider_id:
                del out[key]
        out[alias] = provider_id
        out[provider_id] = provider_id
    return out


def overlay_alias_to_ids(
    config: dict[str, list[str]],
) -> dict[str, list[str]]:
    out = {k: list(v) for k, v in config.items()}
    for provider_id, alias in _overrides.items():
        for key, ids in list(out.items()):
            if key == provider_id:
                continue
            if provider_id in ids:
                ids.remove(provider_id)
                if not ids:
                    del out[key]
        bucket = out.setdefault(alias, [])
        if provider_id not in bucket:
            bucket.append(provider_id)
    return out
