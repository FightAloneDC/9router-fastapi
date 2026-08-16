"""Cerebras usage handler — org-level, per-model caps.

Limits are per organization and per model (not IP). Published
Free Trial vs Developer (payg) tables live on
CerebrasConfig.RATE_LIMITS.

Tracker `used` comes from local usage_history (tokens today for
TPD; requests in the last 60s for RPM). Rate-limit headers
overlay when Cerebras sends them (OpenAI names or *-minute /
*-day suffixes).

Developer tier has no TPH/TPD in docs. Exact org caps:
cloud.cerebras.ai (Limits).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.cerebras.config import CerebrasConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_LIMIT_REQ = "x-ratelimit-limit-requests"
_REMAIN_REQ = "x-ratelimit-remaining-requests"
_RESET_REQ = "x-ratelimit-reset-requests"
_LIMIT_TOK = "x-ratelimit-limit-tokens"
_REMAIN_TOK = "x-ratelimit-remaining-tokens"
_RESET_TOK = "x-ratelimit-reset-tokens"
_LIMIT_REQ_MIN = "x-ratelimit-limit-requests-minute"
_REMAIN_REQ_MIN = "x-ratelimit-remaining-requests-minute"
_LIMIT_TOK_MIN = "x-ratelimit-limit-tokens-minute"
_REMAIN_TOK_MIN = "x-ratelimit-remaining-tokens-minute"
_RESET_TOK_MIN = "x-ratelimit-reset-tokens-minute"

_DUR = re.compile(
    r"(?P<n>\d+(?:\.\d+)?)(?P<u>ms|h|m|s)",
    re.IGNORECASE,
)
_DUR_UNIT = {
    "h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001,
}


def _plan(account_type: str | None) -> str:
    raw = (account_type or "free").strip().lower()
    if raw in ("payg", "subscribe", "developer"):
        return "payg"
    return "free"


def _strip_prefix(model_id: str) -> str:
    raw = (model_id or "").strip()
    if "/" not in raw:
        return raw
    head, rest = raw.split("/", 1)
    if head == "cb":
        return rest
    return raw


def lookup_limits(
    model_id: str,
    account_type: str | None = None,
) -> dict[str, int]:
    """Published caps for a model on this plan."""
    table = CerebrasConfig().RATE_LIMITS
    plan = _plan(account_type)
    key = f"{plan}/{_strip_prefix(model_id)}"
    if key in table:
        return dict(table[key])
    return {}


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


def reset_to_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        ms = float(raw)
        if ms > 1e12:
            ms = ms / 1000.0
        if ms > 1e9:
            return datetime.fromtimestamp(
                ms, tz=timezone.utc,
            ).isoformat()
        if ms < 1e9:
            when = datetime.now(timezone.utc) + timedelta(
                seconds=ms,
            )
            return when.isoformat()
    except ValueError:
        pass
    total = 0.0
    for match in _DUR.finditer(raw):
        unit = match.group("u").lower()
        total += float(match.group("n")) * _DUR_UNIT[unit]
    if total <= 0:
        return raw
    when = datetime.now(timezone.utc) + timedelta(
        seconds=total,
    )
    return when.isoformat()


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


def _row_from_cap(
    label: str,
    metric: str,
    total: int | None,
    remain: int | None,
    reset_at: str | None,
) -> dict | None:
    if total is None:
        return None
    left = remain if remain is not None else total
    return _item(
        f"{label} {metric}",
        used=max(0, total - left),
        total=total,
        reset_at=reset_at,
    )


def published_quota_rows(
    account_type: str | None = None,
) -> list[dict]:
    """Seed tracker from the plan's published model table."""
    plan = _plan(account_type)
    prefix = f"{plan}/"
    rows: list[dict] = []
    table = CerebrasConfig().RATE_LIMITS
    for key, caps in table.items():
        if not key.startswith(prefix):
            continue
        model_id = key[len(prefix):]
        tpd = caps.get("tpd")
        rpm = caps.get("rpm")
        total = tpd if tpd is not None else rpm
        if total is None:
            continue
        metric = "tokens (TPD)" if tpd is not None else (
            "requests (RPM)"
        )
        rows.append(_item(
            f"{model_id} {metric}",
            used=0,
            total=total,
            reset_at=None,
        ))
    return rows


def apply_local_usage(
    account_type: str | None,
    today_by_model: dict[str, dict[str, int]],
    minute_by_model: dict[str, dict[str, int]] | None = None,
    *,
    tpd_reset: str | None = None,
    rpm_reset: str | None = None,
) -> list[dict]:
    """Published bars with local token/request counts."""
    plan = _plan(account_type)
    prefix = f"{plan}/"
    minute = minute_by_model or {}
    rows: list[dict] = []
    table = CerebrasConfig().RATE_LIMITS
    for key, caps in table.items():
        if not key.startswith(prefix):
            continue
        model_id = key[len(prefix):]
        tpd = caps.get("tpd")
        rpm = caps.get("rpm")
        today = today_by_model.get(model_id, {})
        last_min = minute.get(model_id, {})
        if tpd is not None:
            rows.append(_item(
                f"{model_id} tokens (TPD)",
                used=int(today.get("tokens") or 0),
                total=tpd,
                reset_at=tpd_reset,
            ))
            continue
        if rpm is not None:
            rows.append(_item(
                f"{model_id} requests (RPM)",
                used=int(last_min.get("requests") or 0),
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


async def _usage_by_model(
    since: datetime,
    connection_id: str | None,
) -> dict[str, dict[str, int]]:
    """Requests and tokens per Cerebras model since `since`."""
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    cid = _cid_key(connection_id)
    async with async_session() as db:
        cond = [
            func.lower(UsageHistory.provider) == "cerebras",
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


def _first_hdr_int(headers: Any, *keys: str) -> int | None:
    for key in keys:
        value = _hdr_int(headers, key)
        if value is not None:
            return value
    return None


def quotas_from_headers(
    headers: Any,
    model_id: str | None = None,
    account_type: str | None = None,
) -> list[dict]:
    """Config caps plus optional live headers."""
    caps = lookup_limits(model_id or "", account_type)
    req_limit = _first_hdr_int(
        headers, _LIMIT_REQ, _LIMIT_REQ_MIN,
    )
    req_remain = _first_hdr_int(
        headers, _REMAIN_REQ, _REMAIN_REQ_MIN,
    )
    tok_limit = _first_hdr_int(
        headers, _LIMIT_TOK, _LIMIT_TOK_MIN,
    )
    tok_remain = _first_hdr_int(
        headers, _REMAIN_TOK, _REMAIN_TOK_MIN,
    )
    if tok_limit is None:
        tok_limit = caps.get("tpm")
    label = _strip_prefix(model_id or "") or "org"
    reset_req = reset_to_iso(_hdr(headers, _RESET_REQ))
    reset_tok = reset_to_iso(
        _hdr(headers, _RESET_TOK)
        or _hdr(headers, _RESET_TOK_MIN),
    )
    rpm_remain = None
    rpm_reset = None
    if req_remain is not None and (
        req_limit is None or req_limit == caps.get("rpm")
    ):
        rpm_remain = req_remain
        rpm_reset = reset_req
    rows: list[dict] = []
    for row in (
        _row_from_cap(
            label, "requests (RPM)", caps.get("rpm"),
            rpm_remain, rpm_reset,
        ),
        _row_from_cap(
            label, "tokens (TPM)", tok_limit,
            tok_remain, reset_tok,
        ),
        _row_from_cap(
            label, "tokens (TPH)", caps.get("tph"),
            None, None,
        ),
        _row_from_cap(
            label, "tokens (TPD)", caps.get("tpd"),
            None, None,
        ),
    ):
        if row is not None:
            rows.append(row)
    return rows


def merge_live_rows(
    existing: list[dict],
    live: list[dict],
    model_id: str,
    account_type: str | None = None,
) -> list[dict]:
    """Keep the plan catalog; replace one model's live rows."""
    base = existing or published_quota_rows(account_type)
    label = _strip_prefix(model_id)
    prefix = f"{label} "
    kept: list[dict] = []
    inserted = False
    for row in base:
        name = str(row.get("name") or "")
        if name.startswith(prefix):
            if not inserted:
                kept.extend(live)
                inserted = True
            continue
        kept.append(row)
    if not inserted:
        kept.extend(live)
    return kept


def overlay_live_on_published(
    cached: list,
    account_type: str | None = None,
) -> list[dict]:
    result = published_quota_rows(account_type)
    by_label: dict[str, list[dict]] = {}
    for row in cached:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        label = name.split(" requests", 1)[0]
        label = label.split(" tokens", 1)[0]
        by_label.setdefault(label, []).append(row)
    for label, rows in by_label.items():
        live = any(
            int(r.get("used") or 0) > 0
            or r.get("reset_at")
            or "TPM" in str(r.get("name") or "")
            or "requests (RPM)" in str(r.get("name") or "")
            for r in rows
        )
        if live:
            result = merge_live_rows(
                result, rows, label, account_type,
            )
    return result


async def _account_type(db: Any, connection_id: str) -> str:
    from app.models.provider import ProviderConnection

    conn = await db.get(
        ProviderConnection, uuid.UUID(connection_id),
    )
    if conn is None or not conn.data:
        return "free"
    try:
        data = json.loads(conn.data)
    except (json.JSONDecodeError, TypeError):
        return "free"
    return _plan(str(data.get("accountType") or "free"))


class CerebrasUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "cerebras"
    USES_UPSTREAM = False

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        live = _first_hdr_int(
            headers,
            _REMAIN_REQ,
            _REMAIN_TOK,
            _REMAIN_REQ_MIN,
            _REMAIN_TOK_MIN,
        )
        if live is None:
            return
        plan = await _account_type(db, connection_id)
        live_rows = quotas_from_headers(
            headers, model, plan,
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
                existing = [r for r in raw if isinstance(r, dict)]
        rows = merge_live_rows(
            existing or published_quota_rows(plan),
            live_rows,
            model or "",
            plan,
        )
        if cache is None:
            cache = QuotaCache(
                connection_id=uuid.UUID(connection_id),
            )
            db.add(cache)
        cache.plan = plan
        cache.quotas = json.dumps(rows)
        cache.limit_reached = any(
            int(r.get("remaining") or 0) <= 0
            and not r.get("unlimited")
            for r in rows
            if "TPM" in r.get("name", "")
            or "TPD" in r.get("name", "")
            or "RPM" in r.get("name", "")
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
        plan = _plan(str(data.get("accountType") or "free"))
        now = datetime.now(timezone.utc)
        today = await _usage_by_model(
            _today_utc_midnight(), connection_id,
        )
        last_min = await _usage_by_model(
            now - timedelta(seconds=60), connection_id,
        )
        rows = apply_local_usage(
            plan,
            today,
            last_min,
            tpd_reset=_next_utc_midnight_iso(),
            rpm_reset=(now + timedelta(seconds=60)).isoformat(),
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
                    overlay = overlay_live_on_published(
                        raw, plan,
                    )
                    by_name = {
                        str(q.get("name") or ""): q
                        for q in overlay
                        if isinstance(q, dict)
                    }
                    for row in rows:
                        cached = by_name.get(row["name"])
                        if cached is None:
                            continue
                        used = int(cached.get("used") or 0)
                        if used > row["used"]:
                            row.update(_item(
                                row["name"],
                                used=used,
                                total=row["total"],
                                reset_at=(
                                    cached.get("reset_at")
                                    or row["reset_at"]
                                ),
                            ))
                    extra = [
                        q for name, q in by_name.items()
                        if name
                        and all(r["name"] != name for r in rows)
                        and (
                            "TPM" in name or "TPH" in name
                        )
                    ]
                    rows.extend(extra)
        return UsageResponse(
            plan=plan,
            quotas=_quota_items(rows),
            limit_reached=any(
                int(r.get("remaining") or 0) <= 0
                and not r.get("unlimited")
                for r in rows
            ),
            message=(
                "Cerebras limits are per organization and model. "
                "Used is counted from local chat logs; remaining "
                "headers overlay when Cerebras sends them. Exact "
                "org: cloud.cerebras.ai."
            ),
        )
