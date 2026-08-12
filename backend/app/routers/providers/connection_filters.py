"""SQL predicates for paginated provider connection filters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.expression import text

from app.models.provider import ProviderConnection

CONNECTED_TEST_STATUSES: frozenset[str] = frozenset(
    {"connected", "success", "active"}
)

TokenIssue = Literal["expired", "refresh_error", "any"]


@dataclass(frozen=True)
class ConnectionListFilters:
    q: str | None = None
    is_active: bool | None = None
    test_status: str | None = None
    auth_type: str | None = None
    has_proxy: bool | None = None
    proxy_pool_id: UUID | str | None = None
    token_issue: TokenIssue | None = None
    in_cooldown: bool | None = None


def _data_jsonb() -> ColumnElement[Any]:
    return cast(ProviderConnection.data, JSONB)


_COOLDOWN_EXISTS_BODY = """
EXISTS (
  SELECT 1
  FROM jsonb_each_text(
    CAST(provider_connections.data AS jsonb)
  ) AS kv(key, value)
  WHERE kv.key LIKE 'modelLock_%'
    AND kv.value <> ''
    AND kv.value > :now_iso
)
"""


def _cooldown_clause(in_cooldown: bool) -> ColumnElement[bool]:
    """Return EXISTS or NOT EXISTS for active modelLock_* cooldown keys."""
    prefix = "" if in_cooldown else "NOT "
    return text(prefix + _COOLDOWN_EXISTS_BODY.strip()).bindparams(
        now_iso=datetime.now(timezone.utc).isoformat()
    )


def build_connection_filter_clause(
    provider_id: str,
    filters: ConnectionListFilters,
) -> ColumnElement[bool]:
    """AND all active filters; always scopes to provider_id."""
    clauses: list[ColumnElement[bool]] = [
        ProviderConnection.provider == provider_id,
    ]
    data = _data_jsonb()

    q = (filters.q or "").strip()
    if q:
        pattern = f"%{q}%"
        display = data["displayName"].as_string()
        clauses.append(
            or_(
                ProviderConnection.name.ilike(pattern),
                ProviderConnection.email.ilike(pattern),
                display.ilike(pattern),
            )
        )

    if filters.is_active is not None:
        clauses.append(
            ProviderConnection.is_active.is_(filters.is_active)
        )

    if filters.auth_type:
        clauses.append(
            ProviderConnection.auth_type == filters.auth_type
        )

    if filters.test_status:
        status = filters.test_status.strip().lower()
        status_col = func.lower(data["testStatus"].as_string())
        if status in CONNECTED_TEST_STATUSES:
            clauses.append(
                status_col.in_(sorted(CONNECTED_TEST_STATUSES))
            )
        else:
            clauses.append(status_col == status)

    if filters.proxy_pool_id is not None:
        clauses.append(
            ProviderConnection.proxy_pool_id
            == filters.proxy_pool_id
        )
    elif filters.has_proxy is True:
        clauses.append(
            ProviderConnection.proxy_pool_id.is_not(None)
        )
    elif filters.has_proxy is False:
        clauses.append(
            ProviderConnection.proxy_pool_id.is_(None)
        )

    if filters.token_issue:
        expires_raw = data["expiresAt"].as_string()
        last_err = data["lastError"].as_string()
        now_iso = datetime.now(timezone.utc).isoformat()
        expired = and_(
            expires_raw.is_not(None),
            expires_raw != "",
            expires_raw < now_iso,
        )
        refresh_err = and_(
            last_err.is_not(None),
            last_err != "",
        )
        if filters.token_issue == "expired":
            clauses.append(expired)
        elif filters.token_issue == "refresh_error":
            clauses.append(refresh_err)
        else:
            clauses.append(or_(expired, refresh_err))

    if filters.in_cooldown is not None:
        clauses.append(_cooldown_clause(filters.in_cooldown))

    return and_(*clauses)
