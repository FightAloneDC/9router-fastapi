"""OpenRouter usage handler — IP-scoped free-model caps.

Published caps live on OpenrouterConfig.RATE_LIMITS (free vs
payg/subscribe). They apply to :free variants per egress IP,
not per API key. Paid models have no platform request cap.

Live remaining: X-RateLimit-* on 429 only (success responses
omit them). Credit remaining is GET /api/v1/key (optional).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.openrouter.config import OpenrouterConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_LIMIT = "x-ratelimit-limit"
_REMAIN = "x-ratelimit-remaining"
_RESET = "x-ratelimit-reset"
_ALIAS = "openrouter"


def _strip_prefix(model_id: str) -> str:
    raw = (model_id or "").strip()
    if "/" not in raw:
        return raw
    head, rest = raw.split("/", 1)
    if head == _ALIAS and "/" in rest:
        return rest
    return raw


def _is_free_variant(model_id: str) -> bool:
    return _strip_prefix(model_id).endswith(":free")


def lookup_limits(
    model_id: str,
    account_type: str | None = None,
) -> dict[str, int]:
    """Published caps for a model (config, not headers)."""
    table = OpenrouterConfig().RATE_LIMITS
    key = _strip_prefix(model_id)
    if key and not _is_free_variant(key):
        return {}
    plan = (account_type or "free").strip().lower()
    if plan not in table:
        plan = "free"
    return dict(table[plan])


def _hdr(headers: Any, key: str) -> str | None:
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    lower = key.lower()
    raw = getter(key)
    if raw is None:
        raw = getter(lower)
    if raw is None:
        items = getattr(headers, "items", None)
        if items is not None:
            for name, value in items():
                if str(name).lower() == lower:
                    raw = value
                    break
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _hdr_int(headers: Any, key: str) -> int | None:
    raw = _hdr(headers, key)
    if raw is None:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _reset_iso(headers: Any) -> str | None:
    raw = _hdr(headers, _RESET)
    if raw is None:
        return None
    try:
        ms = float(raw)
    except ValueError:
        return raw
    if ms > 1e12:
        ms = ms / 1000.0
    try:
        return datetime.fromtimestamp(
            ms, tz=timezone.utc,
        ).isoformat()
    except (OSError, OverflowError, ValueError):
        return raw


def _item(
    name: str,
    *,
    used: int,
    total: int,
    reset_at: str | None,
) -> dict:
    remaining = max(0, total - used)
    pct = 100.0 if total <= 0 else max(
        0.0, remaining / total * 100,
    )
    return {
        "name": name,
        "used": min(used, total) if total else used,
        "total": total,
        "remaining": remaining,
        "remaining_percentage": pct,
        "reset_at": reset_at,
        "unlimited": total <= 0,
    }


def quotas_from_headers(
    headers: Any,
    model_id: str | None = None,
    account_type: str | None = None,
) -> list[dict]:
    """Build quota rows from config caps + optional 429 headers."""
    caps = lookup_limits(model_id or "", account_type)
    hdr_limit = _hdr_int(headers, _LIMIT)
    hdr_remain = _hdr_int(headers, _REMAIN)
    reset_at = _reset_iso(headers)

    rpm = caps.get("rpm")
    rpd = caps.get("rpd")
    if hdr_limit is not None and hdr_remain is not None:
        if rpd is not None and hdr_limit == rpd:
            rpd_remain = hdr_remain
            rpm_remain = rpm
        elif rpm is not None and hdr_limit == rpm:
            rpm_remain = hdr_remain
            rpd_remain = rpd
        else:
            rpm_remain = rpm
            rpd_remain = rpd
    else:
        rpm_remain = rpm
        rpd_remain = rpd

    rows: list[dict] = []
    label = _strip_prefix(model_id or "") or ":free"
    if rpm is not None:
        remain = rpm_remain if rpm_remain is not None else rpm
        rows.append(_item(
            f"{label} requests (RPM)",
            used=max(0, rpm - remain),
            total=rpm,
            reset_at=reset_at if hdr_limit == rpm else None,
        ))
    if rpd is not None:
        remain = rpd_remain if rpd_remain is not None else rpd
        rows.append(_item(
            f"{label} requests (RPD)",
            used=max(0, rpd - remain),
            total=rpd,
            reset_at=reset_at if hdr_limit == rpd else None,
        ))
    if (
        hdr_limit is not None
        and hdr_remain is not None
        and hdr_limit not in {rpm, rpd}
    ):
        rows.append(_item(
            f"{label} requests (header)",
            used=max(0, hdr_limit - hdr_remain),
            total=hdr_limit,
            reset_at=reset_at,
        ))
    return rows


def apply_local_usage(
    account_type: str,
    rpm_used: int,
    rpd_used: int,
    *,
    rpm_reset: str | None = None,
    rpd_reset: str | None = None,
) -> list[dict]:
    """Published :free caps with locally counted requests."""
    caps = lookup_limits("", account_type)
    rows: list[dict] = []
    rpm = caps.get("rpm")
    rpd = caps.get("rpd")
    if rpm is not None:
        rows.append(_item(
            ":free requests (RPM)",
            used=rpm_used,
            total=rpm,
            reset_at=rpm_reset,
        ))
    if rpd is not None:
        rows.append(_item(
            ":free requests (RPD)",
            used=rpd_used,
            total=rpd,
            reset_at=rpd_reset,
        ))
    return rows


def _today_utc_midnight() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_utc_midnight_iso() -> str:
    nxt = _today_utc_midnight() + timedelta(days=1)
    return nxt.isoformat()


async def _count_free_requests(since: datetime) -> int:
    """Count OpenRouter :free chats on this host since `since`."""
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    async with async_session() as db:
        result = await db.execute(
            select(func.count()).select_from(UsageHistory).where(
                UsageHistory.provider == "openrouter",
                UsageHistory.timestamp >= since,
                UsageHistory.model.like("%:free"),
            )
        )
        return int(result.scalar() or 0)


_IP_SCOPE = "quota-ip"
_IP_KEY = "openrouter"


def _quota_items(raw: list) -> list[QuotaItem]:
    items: list[QuotaItem] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        items.append(QuotaItem(**{
            k: v for k, v in row.items()
            if k in QuotaItem.model_fields
        }))
    return items


async def _account_type(
    db: Any, connection_id: str,
) -> str | None:
    from app.models.provider import ProviderConnection

    conn = await db.get(
        ProviderConnection, uuid.UUID(connection_id),
    )
    if conn is None or not conn.data:
        return None
    try:
        blob = json.loads(conn.data)
    except (json.JSONDecodeError, TypeError):
        return None
    raw = blob.get("accountType")
    if not raw:
        return None
    return str(raw)


async def _save_ip_snapshot(
    db: Any,
    plan: str,
    rows: list[dict],
    limit_reached: bool,
) -> None:
    from sqlalchemy import select

    from app.models.settings import KV

    payload = json.dumps({
        "plan": plan,
        "quotas": rows,
        "limit_reached": limit_reached,
    })
    result = await db.execute(
        select(KV).where(
            KV.scope == _IP_SCOPE,
            KV.key == _IP_KEY,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(KV(
            scope=_IP_SCOPE, key=_IP_KEY, value=payload,
        ))
    else:
        row.value = payload


async def _load_ip_or_connection(
    connection_id: str | None,
) -> UsageResponse | None:
    from sqlalchemy import select

    from app.database import async_session
    from app.models.quota_cache import QuotaCache
    from app.models.settings import KV

    async with async_session() as db:
        ip = (
            await db.execute(
                select(KV).where(
                    KV.scope == _IP_SCOPE,
                    KV.key == _IP_KEY,
                )
            )
        ).scalar_one_or_none()
        cache = None
        if connection_id:
            cache = await db.get(
                QuotaCache, uuid.UUID(connection_id),
            )
    if ip is not None and ip.value:
        try:
            data = json.loads(ip.value)
        except (json.JSONDecodeError, TypeError):
            data = {}
        items = _quota_items(data.get("quotas") or [])
        if items:
            return UsageResponse(
                plan=data.get("plan") or "OpenRouter IP",
                quotas=items,
                limit_reached=bool(data.get("limit_reached")),
            )
    if cache is not None and cache.quotas:
        try:
            raw = json.loads(cache.quotas)
        except (json.JSONDecodeError, TypeError):
            raw = []
        items = _quota_items(raw)
        if items:
            return UsageResponse(
                plan=cache.plan or "OpenRouter IP",
                quotas=items,
                limit_reached=bool(cache.limit_reached),
            )
    return None


class OpenrouterUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "openrouter"
    USES_UPSTREAM = False

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        if _hdr_int(headers, _LIMIT) is None:
            return
        account_type = await _account_type(db, connection_id)
        rows = quotas_from_headers(
            headers, model, account_type,
        )
        if not rows:
            return
        from app.models.quota_cache import QuotaCache

        cache = await db.get(
            QuotaCache, uuid.UUID(connection_id),
        )
        if cache is None:
            cache = QuotaCache(
                connection_id=uuid.UUID(connection_id),
            )
            db.add(cache)
        cache.plan = "OpenRouter IP"
        cache.quotas = json.dumps(rows)
        cache.limit_reached = any(
            int(r.get("remaining") or 0) <= 0
            and not r.get("unlimited")
            for r in rows
        )
        cache.fetched_at = datetime.now(timezone.utc)
        await _save_ip_snapshot(
            db, cache.plan, rows, cache.limit_reached,
        )
        await db.commit()

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        data = provider_data or {}
        plan = str(data.get("accountType") or "free")
        now = datetime.now(timezone.utc)
        rpm_used = await _count_free_requests(
            now - timedelta(seconds=60),
        )
        rpd_used = await _count_free_requests(
            _today_utc_midnight(),
        )
        rows = apply_local_usage(
            plan, rpm_used, rpd_used,
            rpd_reset=_next_utc_midnight_iso(),
        )
        cached = await _load_ip_or_connection(connection_id)
        if cached is not None:
            for row in rows:
                metric = (
                    "RPM" if "RPM" in row["name"] else "RPD"
                )
                for q in cached.quotas:
                    if metric not in q.name:
                        continue
                    if q.used > row["used"]:
                        row.update(_item(
                            row["name"],
                            used=q.used,
                            total=row["total"],
                            reset_at=q.reset_at or row["reset_at"],
                        ))
        paid_note = ""
        if rpm_used == 0 and rpd_used == 0:
            paid_note = (
                " Only :free model ids count toward RPM/RPD."
            )
        return UsageResponse(
            plan=plan,
            quotas=_quota_items(rows),
            limit_reached=any(
                int(r.get("remaining") or 0) <= 0
                and not r.get("unlimited")
                for r in rows
            ),
            message=(
                "OpenRouter :free limits are per egress IP "
                "(not per API key). Used is counted from local "
                "chat logs; 429 headers overlay when present."
                + paid_note
            ),
        )
