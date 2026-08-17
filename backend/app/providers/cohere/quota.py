"""Cohere usage handler — summary card + per-model detail.

Chat RPM is per model; rerank/embed are per endpoint; free plan
also has 1000 API calls / month (docs.cohere.com/docs/rate-limits).
List fetch stays tiny (Alibaba Studio pattern).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.cohere.config import CohereConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_LIMIT_REQ = "x-ratelimit-limit-requests"
_REMAIN_REQ = "x-ratelimit-remaining-requests"
_RESET_REQ = "x-ratelimit-reset-requests"


def _plan(account_type: str | None) -> str:
    plan = (account_type or "free").strip().lower()
    if plan not in ("free", "payg", "subscribe"):
        return "free"
    return plan


def _strip_prefix(model_id: str) -> str:
    raw = (model_id or "").strip()
    if "/" not in raw:
        return raw
    head, rest = raw.split("/", 1)
    if head in ("cohere", "co"):
        return rest
    return raw


def lookup_limits(
    model_id: str,
    account_type: str | None = None,
) -> dict[str, int]:
    """Published caps for a model or endpoint id."""
    table = CohereConfig().RATE_LIMITS
    plan = _plan(account_type)
    key = f"{plan}/{_strip_prefix(model_id)}"
    if key in table:
        return dict(table[key])
    return {}


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


def _today_utc_midnight(now: datetime | None = None) -> datetime:
    stamp = now or datetime.now(timezone.utc)
    return stamp.replace(
        hour=0, minute=0, second=0, microsecond=0,
    )


def _next_utc_midnight_iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    nxt = _today_utc_midnight(stamp) + timedelta(days=1)
    return nxt.isoformat()


def _month_start_utc(now: datetime) -> datetime:
    return datetime(
        now.year, now.month, 1, tzinfo=timezone.utc,
    )


def _next_month_start_iso(now: datetime) -> str:
    if now.month == 12:
        nxt = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        nxt = datetime(
            now.year, now.month + 1, 1, tzinfo=timezone.utc,
        )
    return nxt.isoformat()


def summary_quota_rows(
    minute_by_model: dict[str, dict[str, int]],
    *,
    month_used: int = 0,
    account_type: str | None = None,
    reset_at: str | None = None,
    month_reset_at: str | None = None,
) -> list[dict]:
    """Account-level bars for the list card (tiny payload)."""
    req = 0
    tok = 0
    for bucket in minute_by_model.values():
        req += int(bucket.get("requests") or 0)
        tok += int(bucket.get("tokens") or 0)
    rows = [
        _item(
            "requests (last 60s)",
            used=req,
            total=0,
            reset_at=reset_at,
        ),
        _item(
            "tokens (last 60s)",
            used=tok,
            total=0,
            reset_at=reset_at,
        ),
    ]
    if _plan(account_type) == "free":
        table = CohereConfig().RATE_LIMITS
        calls = int(
            table.get("free/_monthly", {}).get("calls") or 1000
        )
        rows.append(_item(
            "calls (month)",
            used=int(month_used),
            total=calls,
            reset_at=month_reset_at,
        ))
    return rows


def apply_local_usage(
    account_type: str | None,
    minute_by_model: dict[str, dict[str, int]],
    today_by_model: dict[str, dict[str, int]] | None = None,
    *,
    rpm_reset: str | None = None,
    today_reset: str | None = None,
) -> list[dict]:
    """Published RPM/IPM (last 60s) + today request counts.

    RPM/IPM use the rate-limit window (60s). Today bars are
    unlimited counters so the detail modal still shows which
    models were used after the minute window rolls off.
    """
    plan = _plan(account_type)
    prefix = f"{plan}/"
    today = today_by_model or {}
    rows: list[dict] = []
    table = CohereConfig().RATE_LIMITS
    for key, caps in table.items():
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix):]
        if suffix == "_monthly":
            continue
        last_min = minute_by_model.get(suffix, {})
        used_req = int(last_min.get("requests") or 0)
        today_req = int(
            (today.get(suffix) or {}).get("requests") or 0,
        )
        rpm = caps.get("rpm")
        ipm = caps.get("ipm")
        if rpm is not None:
            rows.append(_item(
                f"{suffix} requests (RPM)",
                used=used_req,
                total=rpm,
                reset_at=rpm_reset,
            ))
            rows.append(_item(
                f"{suffix} requests (today)",
                used=today_req,
                total=0,
                reset_at=today_reset,
            ))
        if ipm is not None:
            # Local request count proxies embed inputs/min.
            rows.append(_item(
                f"{suffix} inputs (IPM)",
                used=used_req,
                total=ipm,
                reset_at=rpm_reset,
            ))
            rows.append(_item(
                f"{suffix} inputs (today)",
                used=today_req,
                total=0,
                reset_at=today_reset,
            ))
    return rows


def _summary_only(rows: list[dict]) -> list[dict]:
    """Keep account summary bars (incl. monthly)."""
    out: list[dict] = []
    for row in rows:
        name = str(row.get("name") or "")
        if "last 60s" in name or name == "calls (month)":
            out.append(row)
    return out


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


async def _usage_by_model(
    since: datetime,
    connection_id: str | None,
) -> dict[str, dict[str, int]]:
    """Requests and tokens per cohere model since `since`."""
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    cid = _cid_key(connection_id)
    async with async_session() as db:
        cond = [
            func.lower(UsageHistory.provider) == "cohere",
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
            select(
                UsageHistory.model,
                func.count().label("requests"),
                func.coalesce(
                    func.sum(
                        UsageHistory.prompt_tokens
                        + UsageHistory.completion_tokens
                    ),
                    0,
                ).label("tokens"),
            ).where(*cond).group_by(UsageHistory.model)
        )
        out: dict[str, dict[str, int]] = {}
        for model, requests, tokens in result.all():
            label = _strip_prefix(str(model or ""))
            if not label:
                continue
            bucket = out.setdefault(
                label, {"requests": 0, "tokens": 0},
            )
            bucket["requests"] += int(requests or 0)
            bucket["tokens"] += int(tokens or 0)
        return out


async def _count_calls(
    since: datetime,
    connection_id: str | None,
) -> int:
    """Count Cohere API calls since `since` (this connection)."""
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    cid = _cid_key(connection_id)
    async with async_session() as db:
        cond = [
            func.lower(UsageHistory.provider) == "cohere",
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


def quotas_from_headers(
    headers: Any,
    model_id: str | None = None,
    account_type: str | None = None,
) -> list[dict]:
    """Config RPM plus optional live request headers."""
    caps = lookup_limits(model_id or "", account_type)
    req_limit = _hdr_int(headers, _LIMIT_REQ)
    req_remain = _hdr_int(headers, _REMAIN_REQ)
    if req_limit is None:
        req_limit = caps.get("rpm")
    if req_limit is None:
        return []
    if req_remain is None and caps.get("rpm") is None:
        return []
    label = _strip_prefix(model_id or "") or "chat"
    used = (
        max(0, req_limit - req_remain)
        if req_remain is not None
        else 0
    )
    reset_raw = _hdr(headers, _RESET_REQ)
    reset_at = None
    if reset_raw:
        try:
            secs = float(reset_raw)
            reset_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=secs)
            ).isoformat()
        except ValueError:
            reset_at = reset_raw
    return [
        _item(
            f"{label} requests (RPM)",
            used=used,
            total=req_limit,
            reset_at=reset_at,
        ),
    ]


def merge_live_rows(
    existing: list[dict],
    live: list[dict],
    model_id: str,
) -> list[dict]:
    """Keep summary bars; attach last-model live RPM only."""
    base = _summary_only(existing or [])
    label = _strip_prefix(model_id)
    prefix = f"{label} "
    kept: list[dict] = list(base)
    for row in existing or []:
        name = str(row.get("name") or "")
        if name.startswith(prefix):
            continue
        if "last 60s" in name or name == "calls (month)":
            continue
        if " requests (RPM)" in name or " inputs (IPM)" in name:
            continue
        kept.append(row)
    kept.extend(live)
    return kept


class CohereUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "cohere"
    USES_UPSTREAM = False

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        if _hdr_int(headers, _REMAIN_REQ) is None:
            return
        live_rows = quotas_from_headers(
            headers, model, "free",
        )
        if not live_rows:
            return
        from app.models.quota_cache import QuotaCache

        cache = await db.get(
            QuotaCache, uuid.UUID(connection_id),
        )
        existing: list[dict] = []
        if cache is not None and cache.quotas:
            try:
                raw = json.loads(cache.quotas)
            except (json.JSONDecodeError, TypeError):
                raw = []
            if isinstance(raw, list):
                existing = [
                    r for r in raw if isinstance(r, dict)
                ]
        rows = merge_live_rows(
            existing, live_rows, model or "",
        )
        if cache is None:
            cache = QuotaCache(
                connection_id=uuid.UUID(connection_id),
            )
            db.add(cache)
        cache.plan = cache.plan or "free"
        cache.quotas = json.dumps(rows)
        cache.limit_reached = any(
            int(r.get("remaining") or 0) <= 0
            and not r.get("unlimited")
            for r in rows
            if "RPM" in r.get("name", "")
            or r.get("name") == "calls (month)"
        )
        cache.fetched_at = datetime.now(timezone.utc)
        await db.commit()

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        del access_token
        data = provider_data or {}
        plan = _plan(str(data.get("accountType") or "free"))
        now = datetime.now(timezone.utc)
        last_min = await _usage_by_model(
            now - timedelta(seconds=60), connection_id,
        )
        month_used = 0
        month_reset = None
        if plan == "free":
            month_used = await _count_calls(
                _month_start_utc(now), connection_id,
            )
            month_reset = _next_month_start_iso(now)
        reset = (now + timedelta(seconds=60)).isoformat()
        rows = summary_quota_rows(
            last_min,
            month_used=month_used,
            account_type=plan,
            reset_at=reset,
            month_reset_at=month_reset,
        )
        limit_reached = any(
            int(r.get("remaining") or 0) <= 0
            and not r.get("unlimited")
            for r in rows
        )
        return UsageResponse(
            plan=plan,
            quotas=_quota_items(rows),
            limit_reached=limit_reached,
            message=(
                "Cohere Chat limits are per model. Card shows "
                "local usage for the last 60s"
                + (
                    " and monthly calls (free/trial)."
                    if plan == "free"
                    else "."
                )
                + " Open Model details for per-model RPM."
            ),
        )

    async def fetch_model_details(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        """Full per-model table for the detail modal (not cached)."""
        del access_token
        data = provider_data or {}
        plan = _plan(str(data.get("accountType") or "free"))
        now = datetime.now(timezone.utc)
        last_min = await _usage_by_model(
            now - timedelta(seconds=60), connection_id,
        )
        today = await _usage_by_model(
            _today_utc_midnight(now), connection_id,
        )
        rows = apply_local_usage(
            plan,
            last_min,
            today,
            rpm_reset=(
                now + timedelta(seconds=60)
            ).isoformat(),
            today_reset=_next_utc_midnight_iso(now),
        )
        return UsageResponse(
            plan=plan,
            quotas=_quota_items(rows),
            limit_reached=any(
                int(r.get("remaining") or 0) <= 0
                and not r.get("unlimited")
                for r in rows
                if "RPM" in r.get("name", "")
                or "IPM" in r.get("name", "")
            ),
            message=(
                "RPM/IPM = last 60s vs published caps. "
                "requests (today) = local logs since UTC "
                "midnight (unlimited). Not cached."
            ),
        )
