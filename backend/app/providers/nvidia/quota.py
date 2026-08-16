"""NVIDIA NIM usage handler — free-tier RPM from config + logs.

integrate.api.nvidia.com (free NIM) documents ~40 RPM. There is no
published per-model table and no usage API. Success and 429 responses
often omit X-RateLimit-* and Retry-After.

Used RPM is counted from local usage_history for this connection
(per API key). Headers overlay remaining when NVIDIA actually sends
them.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.nvidia.config import NvidiaConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_LIMIT = "x-ratelimit-limit"
_REMAIN = "x-ratelimit-remaining"
_RESET = "x-ratelimit-reset"
_LIMIT_REQ = "x-ratelimit-limit-requests"
_REMAIN_REQ = "x-ratelimit-remaining-requests"
_RESET_REQ = "x-ratelimit-reset-requests"


def lookup_limits(account_type: str | None = None) -> dict[str, int]:
    """Published caps for the NIM plan (config, not headers)."""
    table = NvidiaConfig().RATE_LIMITS
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
    raw = _hdr(headers, _RESET) or _hdr(headers, _RESET_REQ)
    if raw is None:
        raw = _hdr(headers, "retry-after")
    if raw is None:
        return None
    try:
        ms = float(raw)
    except ValueError:
        return raw
    if ms > 1e12:
        ms = ms / 1000.0
    if ms < 1e9:
        when = datetime.now(timezone.utc) + timedelta(
            seconds=ms,
        )
        return when.isoformat()
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
    account_type: str | None = None,
) -> list[dict]:
    """Config RPM plus optional rate-limit headers."""
    caps = lookup_limits(account_type)
    rpm = caps.get("rpm")
    hdr_limit = _hdr_int(headers, _LIMIT)
    if hdr_limit is None:
        hdr_limit = _hdr_int(headers, _LIMIT_REQ)
    hdr_remain = _hdr_int(headers, _REMAIN)
    if hdr_remain is None:
        hdr_remain = _hdr_int(headers, _REMAIN_REQ)
    reset_at = _reset_iso(headers)
    rows: list[dict] = []
    if rpm is not None:
        remain = rpm
        used_reset = None
        if (
            hdr_remain is not None
            and (hdr_limit is None or hdr_limit == rpm)
        ):
            remain = hdr_remain
            used_reset = reset_at
        rows.append(_item(
            "NIM requests (RPM)",
            used=max(0, rpm - remain),
            total=rpm,
            reset_at=used_reset,
        ))
    if (
        hdr_limit is not None
        and hdr_remain is not None
        and hdr_limit != rpm
    ):
        rows.append(_item(
            "NIM requests (header)",
            used=max(0, hdr_limit - hdr_remain),
            total=hdr_limit,
            reset_at=reset_at,
        ))
    return rows


def apply_local_usage(
    account_type: str,
    rpm_used: int,
    today_used: int = 0,
    *,
    rpm_reset: str | None = None,
    today_reset: str | None = None,
) -> list[dict]:
    """Published RPM cap plus today's chat count (no RPD in docs)."""
    caps = lookup_limits(account_type)
    rpm = caps.get("rpm")
    rows: list[dict] = []
    rows.append(_item(
        "NIM requests (today)",
        used=today_used,
        total=0,
        reset_at=today_reset,
    ))
    if rpm is not None:
        rows.append(_item(
            "NIM requests (last 60s / RPM)",
            used=rpm_used,
            total=rpm,
            reset_at=rpm_reset,
        ))
    return rows


def _today_utc_midnight() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(
        hour=0, minute=0, second=0, microsecond=0,
    )


def _next_utc_midnight_iso() -> str:
    nxt = _today_utc_midnight() + timedelta(days=1)
    return nxt.isoformat()


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


def _quota_items(raw: list) -> list[QuotaItem]:
    return [
        QuotaItem(**{
            k: v for k, v in row.items()
            if k in QuotaItem.model_fields
        })
        for row in raw
        if isinstance(row, dict)
    ]


async def _count_requests(
    since: datetime,
    connection_id: str | None,
) -> int:
    """Count NVIDIA chats since `since` (this key if known)."""
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    cid = _cid_key(connection_id)
    async with async_session() as db:
        cond = [
            func.lower(UsageHistory.provider) == "nvidia",
            UsageHistory.timestamp >= since,
        ]
        if cid:
            stored = func.replace(
                func.lower(
                    func.coalesce(UsageHistory.connection_id, ""),
                ),
                "-",
                "",
            )
            cond.append(stored == cid)
        result = await db.execute(
            select(func.count()).select_from(
                UsageHistory,
            ).where(*cond)
        )
        return int(result.scalar() or 0)


class NvidiaUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "nvidia"
    USES_UPSTREAM = False

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        if (
            _hdr_int(headers, _LIMIT) is None
            and _hdr_int(headers, _LIMIT_REQ) is None
            and _hdr_int(headers, _REMAIN) is None
            and _hdr_int(headers, _REMAIN_REQ) is None
        ):
            return
        rows = quotas_from_headers(headers)
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
        cache.plan = "free"
        cache.quotas = json.dumps(rows)
        cache.limit_reached = any(
            int(r.get("remaining") or 0) <= 0
            and not r.get("unlimited")
            for r in rows
        )
        cache.fetched_at = datetime.now(timezone.utc)
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
        rpm_used = await _count_requests(
            now - timedelta(seconds=60),
            connection_id,
        )
        today_used = await _count_requests(
            _today_utc_midnight(),
            connection_id,
        )
        rows = apply_local_usage(
            plan,
            rpm_used,
            today_used,
            rpm_reset=(
                now + timedelta(seconds=60)
            ).isoformat(),
            today_reset=_next_utc_midnight_iso(),
        )
        if connection_id:
            from app.database import async_session
            from app.models.quota_cache import QuotaCache

            async with async_session() as db:
                cache = await db.get(
                    QuotaCache, uuid.UUID(connection_id),
                )
            if cache is not None and cache.quotas:
                try:
                    raw = json.loads(cache.quotas)
                except (json.JSONDecodeError, TypeError):
                    raw = []
                if isinstance(raw, list):
                    for row in rows:
                        for q in raw:
                            if not isinstance(q, dict):
                                continue
                            name = str(q.get("name") or "")
                            if name != row["name"]:
                                continue
                            used = int(q.get("used") or 0)
                            if used > row["used"]:
                                row.update(_item(
                                    row["name"],
                                    used=used,
                                    total=row["total"],
                                    reset_at=(
                                        q.get("reset_at")
                                        or row["reset_at"]
                                    ),
                                ))
        return UsageResponse(
            plan=plan,
            quotas=_quota_items(rows),
            limit_reached=any(
                int(r.get("remaining") or 0) <= 0
                and not r.get("unlimited")
                for r in rows
            ),
            message=(
                "NVIDIA NIM free-tier cap is ~40 RPM per API key. "
                "Today is local chat count for this connection "
                "(no published daily cap). Last 60s is the RPM "
                "window. Headers overlay when NVIDIA sends them."
            ),
        )
