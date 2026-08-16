"""Groq usage handler — org-level limits from config + headers.

Groq rate limits apply to the organization, not IP or a single
key. Published caps live on GroqConfig.RATE_LIMITS (Developer
plan base). Live remaining comes from success/429 headers:

    x-ratelimit-limit-requests     → RPD
    x-ratelimit-remaining-requests → RPD
    x-ratelimit-reset-requests     → RPD (duration)
    x-ratelimit-limit-tokens       → TPM
    x-ratelimit-remaining-tokens   → TPM
    x-ratelimit-reset-tokens       → TPM (duration)

retry-after is only set on HTTP 429.
RPM/TPD (and whisper ASH/ASD) are published in config only.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.groq.config import GroqConfig
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
    if head == "gq":
        return rest
    return raw


def lookup_limits(model_id: str) -> dict[str, int]:
    """Published caps for a model id (config, not headers)."""
    table = GroqConfig().RATE_LIMITS
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


def reset_to_iso(raw: str | None) -> str | None:
    """Groq reset is a duration (2m59.56s); UI wants ISO."""
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


def published_quota_rows() -> list[dict]:
    """Seed tracker rows from config (no live remaining yet)."""
    rows: list[dict] = []
    table = GroqConfig().RATE_LIMITS
    for model_id, caps in table.items():
        rpd = caps.get("rpd")
        rpm = caps.get("rpm")
        if rpd is None and rpm is None:
            continue
        total = rpd if rpd is not None else rpm
        rows.append(_item(
            f"{model_id} requests (RPD)",
            used=0,
            total=total,
            reset_at=None,
        ))
    return rows


def quotas_from_headers(
    headers: Any,
    model_id: str | None = None,
) -> list[dict]:
    """Build quota rows from Groq headers + config caps."""
    caps = lookup_limits(model_id or "")
    rpd_limit = _hdr_int(headers, _LIMIT_REQ)
    rpd_remain = _hdr_int(headers, _REMAIN_REQ)
    if rpd_limit is None:
        rpd_limit = caps.get("rpd")
    tpm_limit = _hdr_int(headers, _LIMIT_TOK)
    tpm_remain = _hdr_int(headers, _REMAIN_TOK)
    if tpm_limit is None:
        tpm_limit = caps.get("tpm")

    label = _strip_prefix(model_id or "") or "org"
    reset_rpd = reset_to_iso(_hdr(headers, _RESET_REQ))
    reset_tpm = reset_to_iso(_hdr(headers, _RESET_TOK))
    rows: list[dict] = []
    for row in (
        _row_from_cap(
            label, "requests (RPM)", caps.get("rpm"),
            None, None,
        ),
        _row_from_cap(
            label, "requests (RPD)", rpd_limit,
            rpd_remain, reset_rpd,
        ),
        _row_from_cap(
            label, "tokens (TPM)", tpm_limit,
            tpm_remain, reset_tpm,
        ),
        _row_from_cap(
            label, "tokens (TPD)", caps.get("tpd"),
            None, None,
        ),
        _row_from_cap(
            label, "audio (ASH)", caps.get("ash"),
            None, None,
        ),
        _row_from_cap(
            label, "audio (ASD)", caps.get("asd"),
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
) -> list[dict]:
    """Keep the full catalog; replace one model's rows with live."""
    base = existing or published_quota_rows()
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


def overlay_live_on_published(cached: list) -> list[dict]:
    """Heal last-model-only cache back onto the catalog."""
    result = published_quota_rows()
    by_label: dict[str, list[dict]] = {}
    for row in cached:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        label = name.split(" requests", 1)[0]
        label = label.split(" tokens", 1)[0]
        label = label.split(" audio", 1)[0]
        by_label.setdefault(label, []).append(row)
    for label, rows in by_label.items():
        live = any(
            int(r.get("used") or 0) > 0
            or r.get("reset_at")
            or "TPM" in str(r.get("name") or "")
            or "TPD" in str(r.get("name") or "")
            or "requests (RPM)" in str(r.get("name") or "")
            for r in rows
        )
        if live:
            result = merge_live_rows(result, rows, label)
    return result


class GroqUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "groq"
    USES_UPSTREAM = False

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        live = _hdr_int(headers, _REMAIN_REQ)
        if live is None:
            live = _hdr_int(headers, _REMAIN_TOK)
        if live is None:
            return
        live_rows = quotas_from_headers(headers, model)
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
            existing or published_quota_rows(),
            live_rows,
            model or "",
        )
        if cache is None:
            cache = QuotaCache(
                connection_id=uuid.UUID(connection_id),
            )
            db.add(cache)
        cache.plan = "Groq org"
        cache.quotas = json.dumps(rows)
        cache.limit_reached = any(
            int(r.get("remaining") or 0) <= 0
            and not r.get("unlimited")
            for r in rows
            if "RPD" in r.get("name", "")
            or "TPM" in r.get("name", "")
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
        plan = "Groq org"
        if connection_id:
            from app.models.quota_cache import QuotaCache
            from app.database import async_session

            async with async_session() as db:
                cache = await db.get(
                    QuotaCache, uuid.UUID(connection_id),
                )
            if cache is not None and cache.quotas:
                try:
                    raw = json.loads(cache.quotas)
                except (json.JSONDecodeError, TypeError):
                    raw = []
                items = [
                    QuotaItem(**{
                        k: v for k, v in row.items()
                        if k in QuotaItem.model_fields
                    })
                    for row in overlay_live_on_published(raw)
                ]
                if items:
                    return UsageResponse(
                        plan=cache.plan or plan,
                        quotas=items,
                        limit_reached=bool(cache.limit_reached),
                    )
        return UsageResponse(
            plan=plan,
            quotas=[
                QuotaItem(**{
                    k: v for k, v in row.items()
                    if k in QuotaItem.model_fields
                })
                for row in published_quota_rows()
            ],
            message=(
                "Groq limits are per organization (not IP). "
                "Bars are published Developer caps; remaining "
                "updates from rate-limit headers after a chat."
            ),
        )
