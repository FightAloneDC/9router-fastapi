"""Voyage AI usage — summary card + per-model modal.

Official units (retrieved 2026-08-25):

- pricing.md: lifetime free-token grant per current model
  (200M or 50M). Older models have none. Exhausting the grant
  starts billing; it does not 429. Batch API does not consume it.
- rate-limits.md: org tier-1 RPM + TPM per model. Over-limit is
  HTTP 429. No remaining headers and no usage API.

List `fetch` shows three finite free-tier maxima: free tokens
(max 200M), RPM (max 2000), TPM (max 16M). `fetch_model_details`
holds per-model grants and RPM/TPM. `used` is this API key in
`usage_history`. Other org keys are dashboard-only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.voyage_ai.config import VoyageAiConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_CONFIG = VoyageAiConfig()


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


def _strip_prefix(model_id: str) -> str:
    raw = (model_id or "").strip()
    if "/" not in raw:
        return raw
    head, rest = raw.split("/", 1)
    if head in (_CONFIG.PROVIDER_ID, _CONFIG.ALIAS):
        return rest
    return raw


def lookup_limits(model_id: str) -> dict[str, int]:
    """Tier-1 RPM/TPM. Empty when the official table has no row."""
    table = _CONFIG.RATE_LIMITS
    return dict(table.get(_strip_prefix(model_id), {}))


def lookup_free_tokens(model_id: str) -> int | None:
    """Lifetime free-token grant, or None when unpublished."""
    table = _CONFIG.FREE_TOKENS
    total = table.get(_strip_prefix(model_id))
    if total is None:
        return None
    return int(total)


def _default_card_caps() -> dict[str, int]:
    """Tier-1 / free-tier defaults for the list card.

    Per-model nuance lives in the modal. The card uses the published
    maxima so the UI shows finite bars instead of 0/∞.
    """
    rpm = 0
    tpm = 0
    for caps in _CONFIG.RATE_LIMITS.values():
        rpm = max(rpm, int(caps.get("rpm") or 0))
        tpm = max(tpm, int(caps.get("tpm") or 0))
    free = 0
    for grant in _CONFIG.FREE_TOKENS.values():
        free = max(free, int(grant or 0))
    if free <= 0:
        free = 200_000_000
    return {"rpm": rpm, "tpm": tpm, "free_tokens": free}


def _item(
    name: str,
    *,
    used: int,
    total: int,
    reset_at: str | None,
) -> dict[str, Any]:
    remaining = max(0, total - used) if total else 0
    if total <= 0:
        pct = 100.0
    else:
        pct = remaining / total * 100
    return {
        "name": name,
        "used": min(used, total) if total else used,
        "total": total,
        "remaining": remaining,
        "remaining_percentage": pct,
        "reset_at": reset_at,
        "unlimited": total <= 0,
    }


def _quota_items(raw: list[dict[str, Any]]) -> list[QuotaItem]:
    return [QuotaItem(**row) for row in raw]


def summary_quota_rows(
    minute_by_model: dict[str, dict[str, int]],
    *,
    lifetime_tokens: int = 0,
    reset_at: str | None = None,
) -> list[dict[str, Any]]:
    """Account-level bars for the list card (finite free-tier caps)."""
    caps = _default_card_caps()
    req = 0
    tok = 0
    for bucket in minute_by_model.values():
        req += int(bucket.get("requests") or 0)
        tok += int(bucket.get("tokens") or 0)
    return [
        _item(
            "free tokens",
            used=int(lifetime_tokens),
            total=int(caps["free_tokens"]),
            reset_at=None,
        ),
        _item(
            "RPM",
            used=req,
            total=int(caps["rpm"]),
            reset_at=reset_at,
        ),
        _item(
            "TPM",
            used=tok,
            total=int(caps["tpm"]),
            reset_at=reset_at,
        ),
    ]


def free_token_bars(
    lifetime_by_model: dict[str, int],
) -> list[dict[str, Any]]:
    """Per-model lifetime grant from pricing.md."""
    rows: list[dict[str, Any]] = []
    grants = _CONFIG.FREE_TOKENS
    for model_id, total in sorted(grants.items()):
        rows.append(_item(
            f"{model_id} free tokens",
            used=int(lifetime_by_model.get(model_id) or 0),
            total=int(total),
            reset_at=None,
        ))
    return rows


def tier1_minute_bars(
    minute_by_model: dict[str, dict[str, int]],
    now: datetime,
) -> list[dict[str, Any]]:
    """One RPM bar and one TPM bar per official table row."""
    reset_at = (now + timedelta(seconds=60)).isoformat()
    rows: list[dict[str, Any]] = []
    for model_id, caps in sorted(_CONFIG.RATE_LIMITS.items()):
        used = minute_by_model.get(model_id, {})
        rows.append(_item(
            f"{model_id} RPM",
            used=int(used.get("requests") or 0),
            total=int(caps["rpm"]),
            reset_at=reset_at,
        ))
        rows.append(_item(
            f"{model_id} TPM",
            used=int(used.get("tokens") or 0),
            total=int(caps["tpm"]),
            reset_at=reset_at,
        ))
    return rows


def model_detail_rows(
    lifetime_by_model: dict[str, int],
    minute_by_model: dict[str, dict[str, int]],
    now: datetime,
) -> list[dict[str, Any]]:
    """Per model: free-token grant, then RPM, then TPM."""
    grants = _CONFIG.FREE_TOKENS
    limits = _CONFIG.RATE_LIMITS
    reset_at = (now + timedelta(seconds=60)).isoformat()
    rows: list[dict[str, Any]] = []
    for model_id in sorted(set(grants) | set(limits)):
        grant = grants.get(model_id)
        if grant is not None:
            rows.append(_item(
                f"{model_id} free tokens",
                used=int(lifetime_by_model.get(model_id) or 0),
                total=int(grant),
                reset_at=None,
            ))
        caps = limits.get(model_id)
        if not caps:
            continue
        used = minute_by_model.get(model_id, {})
        rows.append(_item(
            f"{model_id} RPM",
            used=int(used.get("requests") or 0),
            total=int(caps["rpm"]),
            reset_at=reset_at,
        ))
        rows.append(_item(
            f"{model_id} TPM",
            used=int(used.get("tokens") or 0),
            total=int(caps["tpm"]),
            reset_at=reset_at,
        ))
    return rows


async def _usage_by_model(
    connection_id: str | None,
    *,
    since: datetime | None = None,
) -> dict[str, dict[str, int]]:
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    conditions = [
        func.lower(UsageHistory.provider) == _CONFIG.PROVIDER_ID,
    ]
    if since is not None:
        conditions.append(UsageHistory.timestamp >= since)
    connection_key = _cid_key(connection_id)
    if connection_key:
        stored = func.replace(
            func.lower(func.coalesce(UsageHistory.connection_id, "")),
            "-",
            "",
        )
        conditions.append(stored == connection_key)

    async with async_session() as db:
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
            ).where(*conditions).group_by(UsageHistory.model)
        )
        rows: dict[str, dict[str, int]] = {}
        for model, requests, tokens in result.all():
            key = _strip_prefix(str(model or ""))
            if not key:
                continue
            bucket = rows.setdefault(
                key, {"requests": 0, "tokens": 0},
            )
            bucket["requests"] += int(requests or 0)
            bucket["tokens"] += int(tokens or 0)
        return rows


class VoyageAiUsageHandler(BaseUsageHandler):
    """Voyage card summary plus on-demand per-model detail."""

    PROVIDER_ID = _CONFIG.PROVIDER_ID
    USES_UPSTREAM = False

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        del access_token, provider_data
        now = datetime.now(timezone.utc)
        minute = await _usage_by_model(
            connection_id,
            since=now - timedelta(seconds=60),
        )
        lifetime = await _usage_by_model(connection_id)
        lifetime_tokens = sum(
            int(bucket.get("tokens") or 0)
            for bucket in lifetime.values()
        )
        rows = summary_quota_rows(
            minute,
            lifetime_tokens=lifetime_tokens,
            reset_at=(now + timedelta(seconds=60)).isoformat(),
        )
        return UsageResponse(
            plan="tier-1",
            quotas=_quota_items(rows),
            limit_reached=any(
                int(row["remaining"]) <= 0
                and not row.get("unlimited")
                for row in rows
                if row["name"] in ("RPM", "TPM")
            ),
            message=(
                "Card uses free-tier maxima: free tokens "
                "(pricing.md, max 200M), RPM/TPM (rate-limits.md "
                "tier-1 maxima). Open Model details for per-model "
                "50M/200M grants and per-model RPM/TPM."
            ),
        )

    async def fetch_model_details(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        """Free-token grants plus RPM/TPM for the detail modal."""
        del access_token, provider_data
        now = datetime.now(timezone.utc)
        minute = await _usage_by_model(
            connection_id,
            since=now - timedelta(seconds=60),
        )
        lifetime = await _usage_by_model(connection_id)
        lifetime_tokens = {
            model: int(bucket.get("tokens") or 0)
            for model, bucket in lifetime.items()
        }
        rows = model_detail_rows(lifetime_tokens, minute, now)
        return UsageResponse(
            plan="tier-1",
            quotas=_quota_items(rows),
            limit_reached=any(
                int(row["remaining"]) <= 0
                and not row.get("unlimited")
                and (
                    row["name"].endswith(" RPM")
                    or row["name"].endswith(" TPM")
                )
                for row in rows
            ),
            message=(
                "Free tokens = this API key, all time, vs "
                "pricing.md grant. RPM/TPM = last 60s vs "
                "tier-1 rate-limits.md. Grant exhaustion starts "
                "billing, it does not 429. Batch API does not "
                "use the grant. Other org keys: "
                "dashboard.voyageai.com."
            ),
        )
