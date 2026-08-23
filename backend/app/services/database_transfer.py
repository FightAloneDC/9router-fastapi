"""FK-safe database export/import for infra migration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import ProviderConnection, ProviderNode
from app.models.provider_alias import ProviderAlias
from app.models.provider_model import ProviderModel
from app.models.proxy_pool import ProxyPool
from app.models.quota_cache import QuotaCache
from app.routers.providers.connection_filters import (
    ConnectionListFilters,
    build_export_filter_clause,
)
from app.services.connection_health import (
    classify_health,
    parse_connection_data,
)

EXPORT_VERSION = 1

IMPORT_MODE_REPLACE = "replace_all"
IMPORT_MODE_MERGE = "merge_providers"

HEALTH_TIERS = frozenset(
    {"healthy", "rate_limited", "cooldown", "exhausted", "dead"},
)

# Parents before children on import; truncate uses reverse order.
IMPORT_ORDER: list[str] = [
    "settings",
    "users",
    "kv",
    "proxy_pools",
    "provider_nodes",
    "provider_aliases",
    "provider_models",
    "provider_connections",
    "quota_cache",
    "api_keys",
    "combos",
    "cli_tool_configs",
    "mitm_config",
    "usage_daily",
    "usage_history",
    "request_details",
    "chat_conversations",
    "chat_messages",
    "mitm_logs",
]

CONNECTIONS_TABLES: list[str] = [
    "proxy_pools",
    "provider_nodes",
    "provider_aliases",
    "provider_models",
    "provider_connections",
    "quota_cache",
]


@dataclass(frozen=True)
class ConnectionExportOptions:
    """Filters for selective connection export."""

    providers: list[str] | None = None
    filters: ConnectionListFilters = ConnectionListFilters()
    health: str | None = None
    include_catalog: bool = True
    include_quota: bool = True


def _collect_ids(rows: list[dict[str, Any]], key: str) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        value = row.get(key)
        if value is not None:
            ids.add(str(value))
    return ids


def _build_import_context(tables: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    return {
        "proxy_pool_ids": _collect_ids(tables.get("proxy_pools", []), "id"),
        "connection_ids": _collect_ids(
            tables.get("provider_connections", []),
            "id",
        ),
    }


def _sanitize_rows(
    table: str,
    rows: list[dict[str, Any]],
    ctx: dict[str, set[str]],
) -> list[dict[str, Any]]:
    if table == "provider_connections":
        pool_ids = ctx.get("proxy_pool_ids", set())
        sanitized: list[dict[str, Any]] = []
        for row in rows:
            clean = dict(row)
            pool_id = clean.get("proxy_pool_id")
            if pool_id is not None and str(pool_id) not in pool_ids:
                clean["proxy_pool_id"] = None
            sanitized.append(clean)
        return sanitized

    if table == "quota_cache":
        conn_ids = ctx.get("connection_ids", set())
        return [
            row
            for row in rows
            if str(row.get("connection_id")) in conn_ids
        ]

    return rows


def _connection_matches_health(conn: ProviderConnection, health: str) -> bool:
    data = parse_connection_data(conn)
    tier, _ = classify_health(data)
    return tier == health


def _row_dict(row: Any) -> dict[str, Any]:
    """ORM model or SQLAlchemy row → plain dict for JSON export."""
    table = getattr(row, "__table__", None)
    if table is not None:
        return {col.key: getattr(row, col.key) for col in table.columns}
    return dict(row)


async def _insert_rows(
    db: AsyncSession,
    table: str,
    rows: list[dict[str, Any]],
    parse_datetimes: Any,
) -> int:
    count = 0
    for row in parse_datetimes(rows):
        clean = {k: v for k, v in row.items() if v is not None}
        if not clean:
            continue
        cols = ", ".join(clean.keys())
        placeholders = ", ".join([f":{k}" for k in clean.keys()])
        await db.execute(
            text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"),
            clean,
        )
        count += 1
    return count


async def export_tables(
    db: AsyncSession,
    table_names: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Read rows from the given tables."""
    result: dict[str, list[dict[str, Any]]] = {}
    for table in table_names:
        rows = (await db.execute(text(f"SELECT * FROM {table}"))).mappings().all()
        result[table] = [dict(r) for r in rows]
    return result


async def export_connections_filtered(
    db: AsyncSession,
    options: ConnectionExportOptions,
) -> dict[str, list[dict[str, Any]]]:
    """Export connections and related rows matching filters."""
    health = (options.health or "").strip().lower() or None
    if health and health not in HEALTH_TIERS:
        raise ValueError(f"Invalid health tier: {health}")

    providers = options.providers or None
    where = build_export_filter_clause(options.filters, providers)
    result = await db.execute(select(ProviderConnection).where(where))
    connections = list(result.scalars().all())

    if health:
        connections = [
            c for c in connections if _connection_matches_health(c, health)
        ]

    conn_rows = [_row_dict(c) for c in connections]
    provider_ids = list({c.provider for c in connections})

    pool_uuid_ids = [
        c.proxy_pool_id for c in connections if c.proxy_pool_id is not None
    ]
    node_ids = set(provider_ids)

    tables: dict[str, list[dict[str, Any]]] = {
        "provider_connections": conn_rows,
    }

    if pool_uuid_ids:
        pools = await db.execute(
            select(ProxyPool).where(ProxyPool.id.in_(pool_uuid_ids)),
        )
        tables["proxy_pools"] = [_row_dict(p) for p in pools.scalars().all()]
    else:
        tables["proxy_pools"] = []

    if node_ids:
        nodes = await db.execute(
            select(ProviderNode).where(ProviderNode.id.in_(list(node_ids))),
        )
        tables["provider_nodes"] = [_row_dict(n) for n in nodes.scalars().all()]
    else:
        tables["provider_nodes"] = []

    if options.include_catalog and provider_ids:
        models = await db.execute(
            select(ProviderModel).where(
                ProviderModel.provider.in_(provider_ids),
            ),
        )
        tables["provider_models"] = [
            _row_dict(m) for m in models.scalars().all()
        ]
        aliases = await db.execute(
            select(ProviderAlias).where(
                ProviderAlias.provider.in_(provider_ids),
            ),
        )
        tables["provider_aliases"] = [
            _row_dict(a) for a in aliases.scalars().all()
        ]
    else:
        tables["provider_models"] = []
        tables["provider_aliases"] = []

    if options.include_quota and connections:
        conn_uuid_ids = [c.id for c in connections]
        quotas = await db.execute(
            select(QuotaCache).where(
                QuotaCache.connection_id.in_(conn_uuid_ids),
            ),
        )
        tables["quota_cache"] = [_row_dict(q) for q in quotas.scalars().all()]
    else:
        tables["quota_cache"] = []

    return tables


def build_export_payload(
    tables: dict[str, list[dict[str, Any]]],
    scope: str,
    filters: dict[str, Any] | None = None,
    import_mode: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "export_version": EXPORT_VERSION,
        "scope": scope,
        "tables": tables,
    }
    if filters:
        payload["filters"] = filters
    if import_mode:
        payload["import_mode"] = import_mode
    return payload


def _providers_from_payload(
    tables: dict[str, list[dict[str, Any]]],
    filters: dict[str, Any] | None,
) -> list[str]:
    if filters and filters.get("providers"):
        raw = filters["providers"]
        if isinstance(raw, list):
            return [str(p) for p in raw if p]
    conn_rows = tables.get("provider_connections", [])
    return list({str(r["provider"]) for r in conn_rows if r.get("provider")})


async def import_tables(
    db: AsyncSession,
    tables: dict[str, list[dict[str, Any]]],
    allowed_tables: list[str],
    parse_datetimes: Any,
) -> dict[str, int]:
    """Truncate and insert tables in FK-safe order (full replace)."""
    ordered = [t for t in IMPORT_ORDER if t in allowed_tables and t in tables]
    ctx = _build_import_context(tables)
    imported: dict[str, int] = {}

    for table in reversed(ordered):
        await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

    for table in ordered:
        rows = tables.get(table, [])
        sanitized = _sanitize_rows(table, rows, ctx)
        imported[table] = await _insert_rows(
            db, table, sanitized, parse_datetimes,
        )

    return imported


async def import_connections_merge(
    db: AsyncSession,
    tables: dict[str, list[dict[str, Any]]],
    parse_datetimes: Any,
    filters: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Upsert exported providers without wiping unrelated providers."""
    providers = _providers_from_payload(tables, filters)
    ctx = _build_import_context(tables)
    imported: dict[str, int] = {}

    pool_ids = list(_collect_ids(tables.get("proxy_pools", []), "id"))
    node_ids = list(_collect_ids(tables.get("provider_nodes", []), "id"))

    if pool_ids:
        await db.execute(
            delete(ProxyPool).where(ProxyPool.id.in_(pool_ids)),
        )
    if node_ids:
        await db.execute(
            delete(ProviderNode).where(ProviderNode.id.in_(node_ids)),
        )
    if providers:
        await db.execute(
            delete(ProviderConnection).where(
                ProviderConnection.provider.in_(providers),
            ),
        )
        await db.execute(
            delete(ProviderModel).where(
                ProviderModel.provider.in_(providers),
            ),
        )
        await db.execute(
            delete(ProviderAlias).where(
                ProviderAlias.provider.in_(providers),
            ),
        )

    merge_order = [
        t for t in CONNECTIONS_TABLES if t in tables
    ]
    for table in merge_order:
        rows = tables.get(table, [])
        sanitized = _sanitize_rows(table, rows, ctx)
        imported[table] = await _insert_rows(
            db, table, sanitized, parse_datetimes,
        )

    return imported


async def import_connections_data(
    db: AsyncSession,
    tables: dict[str, list[dict[str, Any]]],
    parse_datetimes: Any,
    import_mode: str = IMPORT_MODE_REPLACE,
    filters: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Import connections export — replace all or merge by provider."""
    if import_mode == IMPORT_MODE_MERGE:
        return await import_connections_merge(
            db, tables, parse_datetimes, filters,
        )
    return await import_tables(
        db,
        tables,
        CONNECTIONS_TABLES,
        parse_datetimes,
    )


def export_options_to_filters_dict(
    options: ConnectionExportOptions,
) -> dict[str, Any]:
    """Serialize export options for JSON payload."""
    payload: dict[str, Any] = {
        "include_catalog": options.include_catalog,
        "include_quota": options.include_quota,
    }
    if options.providers:
        payload["providers"] = options.providers
    if options.health:
        payload["health"] = options.health
    filt = options.filters
    if filt.is_active is not None:
        payload["is_active"] = filt.is_active
    if filt.test_status:
        payload["test_status"] = filt.test_status
    if filt.auth_type:
        payload["auth_type"] = filt.auth_type
    if filt.has_proxy is not None:
        payload["has_proxy"] = filt.has_proxy
    if filt.in_cooldown is not None:
        payload["in_cooldown"] = filt.in_cooldown
    if filt.token_issue:
        payload["token_issue"] = filt.token_issue
    if filt.q:
        payload["q"] = filt.q
    return payload
