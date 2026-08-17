"""Mistral usage handler — org-level, numbers in console Limits.

Public docs: RPS, tokens per minute, tokens per month at
organization level. Free mode vs Scale tiers. No published
numeric table. Tracker `used` comes from usage_history for this
connection. Headers overlay when Mistral sends remaining counts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.mistral.config import MistralConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_LIMIT_REQ_MIN = "x-ratelimit-limit-req-minute"
_REMAIN_REQ_MIN = "x-ratelimit-remaining-req-minute"
_LIMIT_TOK_MIN = "x-ratelimit-limit-tokens-minute"
_REMAIN_TOK_MIN = "x-ratelimit-remaining-tokens-minute"

# Minute windows go stale fast; do not show exhausted snapshots forever.
_HEADER_STALE_SEC = 90


def _plan(account_type: str | None) -> str:
    raw = (account_type or "free").strip().lower()
    if raw in ("scale", "payg", "subscribe", "developer"):
        return "scale"
    return "free"


def lookup_limits(
    account_type: str | None = None,
) -> dict[str, int]:
    """Published caps for the Studio plan (often empty)."""
    table = MistralConfig().RATE_LIMITS
    plan = _plan(account_type)
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


def _first_hdr_int(headers: Any, *keys: str) -> int | None:
    for key in keys:
        value = _hdr_int(headers, key)
        if value is not None:
            return value
    return None


def _reset_iso(headers: Any) -> str | None:
    raw = _hdr(headers, "x-ratelimit-reset")
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


def _next_minute_iso() -> str:
    """Reset hint for Mistral per-minute TPM/RPM windows."""
    now = datetime.now(timezone.utc)
    nxt = now.replace(second=0, microsecond=0) + timedelta(
        minutes=1,
    )
    return nxt.isoformat()


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


def _paired_limit_remain(
    headers: Any,
    pairs: tuple[tuple[str, str], ...],
) -> tuple[int, int] | None:
    """Return (limit, remain) from the first matching header pair."""
    for limit_key, remain_key in pairs:
        limit = _hdr_int(headers, limit_key)
        remain = _hdr_int(headers, remain_key)
        if limit is not None and remain is not None:
            return limit, remain
    return None


def quotas_from_headers(
    headers: Any,
    account_type: str | None = None,
) -> list[dict]:
    """Live bars from Mistral per-minute rate-limit headers only.

    Studio sends ``*-req-minute`` / ``*-tokens-minute``. Labels say
    RPM/TPM so the UI is not a cryptic "(header)" row with N/A reset.
    """
    del account_type
    reset_at = _reset_iso(headers) or _next_minute_iso()
    rows: list[dict] = []
    req = _paired_limit_remain(headers, (
        (_LIMIT_REQ_MIN, _REMAIN_REQ_MIN),
    ))
    if req is not None:
        req_limit, req_remain = req
        rows.append(_item(
            "Mistral RPM (per minute)",
            used=max(0, req_limit - req_remain),
            total=req_limit,
            reset_at=reset_at,
        ))
    tok = _paired_limit_remain(headers, (
        (_LIMIT_TOK_MIN, _REMAIN_TOK_MIN),
    ))
    if tok is not None:
        tok_limit, tok_remain = tok
        rows.append(_item(
            "Mistral TPM (per minute)",
            used=max(0, tok_limit - tok_remain),
            total=tok_limit,
            reset_at=reset_at,
        ))
    return rows


def _is_live_header_bar(name: str) -> bool:
    n = (name or "").lower()
    return (
        "(header)" in n
        or "per minute" in n
        or n.startswith("mistral rpm")
        or n.startswith("mistral tpm")
    )

def apply_local_usage(
    today_requests: int,
    today_tokens: int,
    minute_requests: int,
    *,
    today_reset: str | None = None,
    minute_reset: str | None = None,
) -> list[dict]:
    """Local bars; public docs have no numeric daily/RPM table."""
    return [
        _item(
            "Mistral requests (today)",
            used=today_requests,
            total=0,
            reset_at=today_reset,
        ),
        _item(
            "Mistral tokens (today)",
            used=today_tokens,
            total=0,
            reset_at=today_reset,
        ),
        _item(
            "Mistral requests (last 60s)",
            used=minute_requests,
            total=0,
            reset_at=minute_reset,
        ),
    ]


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


def _has_live_headers(headers: Any) -> bool:
    return _first_hdr_int(
        headers,
        _LIMIT_REQ_MIN, _REMAIN_REQ_MIN,
        _LIMIT_TOK_MIN, _REMAIN_TOK_MIN,
    ) is not None


async def _usage_totals(
    since: datetime,
    connection_id: str | None,
) -> tuple[int, int]:
    """Request count and token sum for this Mistral key."""
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    cid = _cid_key(connection_id)
    async with async_session() as db:
        cond = [
            func.lower(UsageHistory.provider) == "mistral",
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
                func.count(),
                func.coalesce(
                    func.sum(
                        UsageHistory.prompt_tokens
                        + UsageHistory.completion_tokens
                    ),
                    0,
                ),
            ).where(*cond)
        )
        row = result.one()
        return int(row[0] or 0), int(row[1] or 0)


class MistralUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "mistral"
    USES_UPSTREAM = False

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        del model
        if not _has_live_headers(headers):
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
        cache.plan = "mistral"
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
        del access_token
        data = provider_data or {}
        plan = _plan(str(data.get("accountType") or "free"))
        now = datetime.now(timezone.utc)
        today_req, today_tok = await _usage_totals(
            _today_utc_midnight(), connection_id,
        )
        minute_req, _minute_tok = await _usage_totals(
            now - timedelta(seconds=60), connection_id,
        )
        rows = apply_local_usage(
            today_req,
            today_tok,
            minute_req,
            today_reset=_next_utc_midnight_iso(),
            minute_reset=(
                now + timedelta(seconds=60)
            ).isoformat(),
        )
        if connection_id:
            from app.database import async_session
            from app.models.quota_cache import QuotaCache

            async with async_session() as db:
                cache = await db.get(
                    QuotaCache, uuid.UUID(connection_id),
                )
            if cache is not None and cache.quotas:
                age = 10_000.0
                if cache.fetched_at is not None:
                    fetched = cache.fetched_at
                    if fetched.tzinfo is None:
                        fetched = fetched.replace(
                            tzinfo=timezone.utc,
                        )
                    age = (now - fetched).total_seconds()
                try:
                    raw = json.loads(cache.quotas)
                except (json.JSONDecodeError, TypeError):
                    raw = []
                if isinstance(raw, list) and age <= _HEADER_STALE_SEC:
                    local_names = {r["name"] for r in rows}
                    for q in raw:
                        if not isinstance(q, dict):
                            continue
                        name = str(q.get("name") or "")
                        if not name or name in local_names:
                            continue
                        if not _is_live_header_bar(name):
                            continue
                        rows.append(q)
        return UsageResponse(
            plan=plan,
            quotas=_quota_items(rows),
            limit_reached=any(
                int(r.get("remaining") or 0) <= 0
                and not r.get("unlimited")
                for r in rows
            ),
            message=(
                "Mistral limits are per organization (RPS / TPM / "
                "month). Exact caps: console Limits. Used is local "
                "chat logs for this key; headers overlay when sent."
            ),
        )
