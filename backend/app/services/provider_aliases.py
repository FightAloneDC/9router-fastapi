"""Provider prefix: DB row wins, else config.ALIAS.

Custom compatible nodes store their public prefix on the node
(``data.prefix``). That prefix is merged here so ``/v1/models``
lists ``farm-a/gpt-4o`` instead of ``openai-compatible-chat-…/gpt-4o``.
"""

from __future__ import annotations

import json

from sqlalchemy import delete, select

from app.models.provider import ProviderNode
from app.models.provider_alias import ProviderAlias

_overrides: dict[str, str] = {}


def set_overrides(mapping: dict[str, str]) -> None:
    """Replace in-memory DB overlay (tests + cache refresh)."""
    global _overrides
    _overrides = {
        str(k): str(v).strip()
        for k, v in mapping.items()
        if str(v).strip()
    }


def node_public_prefix(data: str | None) -> str:
    """Return the node's public model prefix, or empty."""
    try:
        blob = json.loads(data) if data else {}
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(blob, dict):
        return ""
    return str(blob.get("prefix") or "").strip()


async def refresh_from_db(db: object) -> None:
    """Load prefixes: alias table, then custom node ``data.prefix``."""
    mapping: dict[str, str] = {}
    try:
        result = await db.execute(select(ProviderAlias))
        mapping = {
            row.provider: row.alias
            for row in result.scalars().all()
            if row.alias
        }
    except Exception:
        mapping = {}
    try:
        result = await db.execute(select(ProviderNode))
        for node in result.scalars().all():
            prefix = node_public_prefix(node.data)
            if prefix:
                mapping[node.id] = prefix
    except Exception:
        pass
    set_overrides(mapping)


async def upsert_alias(
    db: object,
    provider: str,
    alias: str | None,
) -> None:
    """Set or clear a DB prefix. Empty value deletes the row."""
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
