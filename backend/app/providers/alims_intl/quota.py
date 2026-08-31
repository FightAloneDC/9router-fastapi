"""Alibaba Studio usage handler — per-model International caps.

Published RPM/TPM live on AlimsIntlConfig.RATE_LIMITS (International
scope subset). Limits are per workspace/model, not per API key.

Tracker `used` comes from local usage_history (requests/tokens in
the last 60s for RPM/TPM). Rate-limit headers overlay when
DashScope sends them.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import async_session
from app.models.quota_cache import QuotaCache
from app.models.usage import UsageHistory
from app.providers.alims_intl.config import AlimsIntlConfig
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


def _strip_prefix(model_id: str) -> str:
    raw = (model_id or "").strip()
    if "/" not in raw:
        return raw
    head, rest = raw.split("/", 1)
    if head in ("alims-intl", "ali"):
        return rest
    return raw


def lookup_limits(model_id: str) -> dict[str, int]:
    """Published International caps for a model id."""
    table = AlimsIntlConfig().RATE_LIMITS
    key = _strip_prefix(model_id)
    if key in table:
        return dict(table[key])
    if model_id in table:
        return dict(table[model_id])
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


def _first_hdr_int(headers: Any, *keys: str) -> int | None:
    for key in keys:
        value = _hdr_int(headers, key)
        if value is not None:
            return value
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


def summary_quota_rows(
    minute_by_model: dict[str, dict[str, int]],
    *,
    reset_at: str | None = None,
) -> list[dict]:
    """Account-level bars for the list card (tiny payload)."""
    req = 0
    tok = 0
    for bucket in minute_by_model.values():
        req += int(bucket.get("requests") or 0)
        tok += int(bucket.get("tokens") or 0)
    return [
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


def published_quota_rows() -> list[dict]:
    """Full International table (detail modal only)."""
    rows: list[dict] = []
    table = AlimsIntlConfig().RATE_LIMITS
    for model_id, caps in table.items():
        rpm = caps.get("rpm")
        tpm = caps.get("tpm")
        if rpm is not None:
            rows.append(_item(
                f"{model_id} requests (RPM)",
                used=0,
                total=rpm,
                reset_at=None,
            ))
        if tpm is not None:
            rows.append(_item(
                f"{model_id} tokens (TPM)",
                used=0,
                total=tpm,
                reset_at=None,
            ))
    return rows


def apply_local_usage(
    minute_by_model: dict[str, dict[str, int]],
    *,
    rpm_reset: str | None = None,
) -> list[dict]:
    """Published RPM/TPM bars with local last-minute counts."""
    rows: list[dict] = []
    table = AlimsIntlConfig().RATE_LIMITS
    for model_id, caps in table.items():
        last_min = minute_by_model.get(model_id, {})
        rpm = caps.get("rpm")
        tpm = caps.get("tpm")
        if rpm is not None:
            rows.append(_item(
                f"{model_id} requests (RPM)",
                used=int(last_min.get("requests") or 0),
                total=rpm,
                reset_at=rpm_reset,
            ))
        if tpm is not None:
            rows.append(_item(
                f"{model_id} tokens (TPM)",
                used=int(last_min.get("tokens") or 0),
                total=tpm,
                reset_at=rpm_reset,
            ))
    return rows


def _summary_only(rows: list[dict]) -> list[dict]:
    """Drop fat catalog rows; keep account summary bars."""
    out: list[dict] = []
    for row in rows:
        name = str(row.get("name") or "")
        if "last 60s" in name:
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
    """Requests and tokens per alims-intl model since `since`."""
    cid = _cid_key(connection_id)
    async with async_session() as db:
        cond = [
            func.lower(UsageHistory.provider) == "alims-intl",
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


def quotas_from_headers(
    headers: Any,
    model_id: str | None = None,
) -> list[dict]:
    """Config caps plus optional live headers."""
    caps = lookup_limits(model_id or "")
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
    if req_limit is None:
        req_limit = caps.get("rpm")
    if tok_limit is None:
        tok_limit = caps.get("tpm")
    label = _strip_prefix(model_id or "") or "workspace"
    reset_req = reset_to_iso(_hdr(headers, _RESET_REQ))
    reset_tok = reset_to_iso(
        _hdr(headers, _RESET_TOK)
        or _hdr(headers, _RESET_TOK_MIN),
    )
    rows: list[dict] = []
    for row in (
        _row_from_cap(
            label, "requests (RPM)", req_limit,
            req_remain, reset_req,
        ),
        _row_from_cap(
            label, "tokens (TPM)", tok_limit,
            tok_remain, reset_tok,
        ),
    ):
        if row is not None:
            rows.append(row)
    return rows


def merge_live_rows(
    existing: list[dict],
    live: list[dict],
    model_id: str,
) -> list[dict]:
    """Keep summary bars; replace one model's live rows."""
    base = _summary_only(existing or [])
    label = _strip_prefix(model_id)
    prefix = f"{label} "
    kept: list[dict] = list(base)
    for row in existing or []:
        name = str(row.get("name") or "")
        if name.startswith(prefix):
            continue
        if "last 60s" in name:
            continue
        # Drop legacy full-catalog rows.
        if " requests (RPM)" in name or " tokens (TPM)" in name:
            continue
        kept.append(row)
    kept.extend(live)
    return kept


def overlay_live_on_published(cached: list) -> list[dict]:
    """Apply cached live rows onto the full published catalog."""
    result = published_quota_rows()
    by_label: dict[str, list[dict]] = {}
    for row in cached:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if "last 60s" in name:
            continue
        label = name.split(" requests", 1)[0]
        label = label.split(" tokens", 1)[0]
        by_label.setdefault(label, []).append(row)
    for label, live_rows in by_label.items():
        live = any(
            int(r.get("used") or 0) > 0
            or r.get("reset_at")
            or "TPM" in str(r.get("name") or "")
            or "requests (RPM)" in str(r.get("name") or "")
            for r in live_rows
        )
        if not live:
            continue
        prefix = f"{label} "
        kept: list[dict] = []
        inserted = False
        for row in result:
            name = str(row.get("name") or "")
            if name.startswith(prefix):
                if not inserted:
                    kept.extend(live_rows)
                    inserted = True
                continue
            kept.append(row)
        if not inserted:
            kept.extend(live_rows)
        result = kept
    return result


class AlimsIntlUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "alims-intl"
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
        live_rows = quotas_from_headers(headers, model)
        if not live_rows:
            return
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
            existing,
            live_rows,
            model or "",
        )
        if cache is None:
            cache = QuotaCache(
                connection_id=uuid.UUID(connection_id),
            )
            db.add(cache)
        cache.plan = "International"
        cache.quotas = json.dumps(rows)
        cache.limit_reached = any(
            int(r.get("remaining") or 0) <= 0
            and not r.get("unlimited")
            for r in rows
            if "TPM" in r.get("name", "")
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
        del access_token, provider_data
        now = datetime.now(timezone.utc)
        last_min = await _usage_by_model(
            now - timedelta(seconds=60), connection_id,
        )
        reset = (now + timedelta(seconds=60)).isoformat()
        rows = summary_quota_rows(last_min, reset_at=reset)
        return UsageResponse(
            plan="International",
            quotas=_quota_items(rows),
            limit_reached=False,
            message=(
                "Alibaba Studio limits are per model. Card shows "
                "local usage totals for the last 60s. Open Model "
                "details for per-model RPM/TPM."
            ),
        )

    async def fetch_model_details(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        """Full per-model table for the detail modal (not cached)."""
        del access_token, provider_data
        now = datetime.now(timezone.utc)
        last_min = await _usage_by_model(
            now - timedelta(seconds=60), connection_id,
        )
        rows = apply_local_usage(
            last_min,
            rpm_reset=(now + timedelta(seconds=60)).isoformat(),
        )
        return UsageResponse(
            plan="International",
            quotas=_quota_items(rows),
            limit_reached=any(
                int(r.get("remaining") or 0) <= 0
                and not r.get("unlimited")
                for r in rows
            ),
            message=(
                "Per-model International RPM/TPM from docs. "
                "Used is local chat logs (last 60s)."
            ),
        )
