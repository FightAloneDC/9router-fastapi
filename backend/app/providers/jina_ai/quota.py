"""Jina AI usage — free-token grant + endpoint RPM/TPM.

Official rate limits (https://docs.jina.ai/ llms.txt, retrieved
2026-08-25): Embedding & Reranker APIs share **500 RPM & 1M TPM**
(premium **2k RPM & 5M TPM**). Not per-model. No remaining headers
and no usage API in that doc.

Free-token grant (**10M**): ``operator: 2026-08-25`` — free /
browser-issued keys. Not published on docs.jina.ai.

``USES_UPSTREAM = False``. ``used`` comes from this connection's
``usage_history``. Docs plan names: ``free`` | ``premium``.
UI ``accountType`` ``payg`` / ``subscribe`` map to ``premium``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import async_session
from app.models.usage import UsageHistory
from app.providers.jina_ai.config import JinaAiConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_CONFIG = JinaAiConfig()


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


def resolve_plan(provider_data: dict | None) -> str:
    """Map connection accountType to docs free|premium."""
    raw = ""
    if isinstance(provider_data, dict):
        raw = str(
            provider_data.get("accountType")
            or provider_data.get("account_type")
            or ""
        ).strip().lower()
    return _CONFIG.UI_TO_DOCS_PLAN.get(raw, "free")


def lookup_limits(plan: str) -> dict[str, int]:
    """Endpoint RPM/TPM for the plan (from RATE_LIMITS)."""
    row = _CONFIG.RATE_LIMITS.get(plan) or _CONFIG.RATE_LIMITS["free"]
    return {
        "rpm": int(row.get("rpm") or 0),
        "tpm": int(row.get("tpm") or 0),
    }


def free_token_grant() -> int:
    """Operator free-token grant from RATE_LIMITS['free']['tokens']."""
    row = _CONFIG.RATE_LIMITS.get("free") or {}
    return int(row.get("tokens") or 0)


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


def summary_quota_rows(
    *,
    lifetime_tokens: int,
    minute_requests: int,
    minute_tokens: int,
    plan: str,
    reset_at: str | None,
) -> list[dict[str, Any]]:
    """List-card bars: free-token grant (free plan) + RPM/TPM."""
    caps = lookup_limits(plan)
    rows: list[dict[str, Any]] = []
    if plan == "free":
        rows.append(
            _item(
                "free tokens",
                used=int(lifetime_tokens),
                total=free_token_grant(),
                reset_at=None,
            )
        )
    rows.extend(
        [
            _item(
                "RPM",
                used=int(minute_requests),
                total=int(caps["rpm"]),
                reset_at=reset_at,
            ),
            _item(
                "TPM",
                used=int(minute_tokens),
                total=int(caps["tpm"]),
                reset_at=reset_at,
            ),
        ]
    )
    return rows


async def _usage_totals(
    connection_id: str | None,
    *,
    since: datetime | None = None,
) -> dict[str, int]:
    conditions = [
        func.lower(UsageHistory.provider) == _CONFIG.PROVIDER_ID,
    ]
    if since is not None:
        conditions.append(UsageHistory.timestamp >= since)
    connection_key = _cid_key(connection_id)
    if connection_key:
        stored = func.replace(
            func.lower(
                func.coalesce(UsageHistory.connection_id, "")
            ),
            "-",
            "",
        )
        conditions.append(stored == connection_key)

    async with async_session() as db:
        result = await db.execute(
            select(
                func.count().label("requests"),
                func.coalesce(
                    func.sum(
                        UsageHistory.prompt_tokens
                        + UsageHistory.completion_tokens
                    ),
                    0,
                ).label("tokens"),
            ).where(*conditions)
        )
        row = result.one()
        return {
            "requests": int(row.requests or 0),
            "tokens": int(row.tokens or 0),
        }


class JinaAiUsageHandler(BaseUsageHandler):
    """Local free-token + endpoint RPM/TPM card."""

    PROVIDER_ID = _CONFIG.PROVIDER_ID
    USES_UPSTREAM = False

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        del access_token
        plan = resolve_plan(provider_data)
        now = datetime.now(timezone.utc)
        minute = await _usage_totals(
            connection_id,
            since=now - timedelta(seconds=60),
        )
        lifetime = await _usage_totals(connection_id)
        reset_at = (now + timedelta(seconds=60)).isoformat()
        rows = summary_quota_rows(
            lifetime_tokens=int(lifetime["tokens"]),
            minute_requests=int(minute["requests"]),
            minute_tokens=int(minute["tokens"]),
            plan=plan,
            reset_at=reset_at,
        )
        return UsageResponse(
            plan=plan,
            quotas=[QuotaItem(**row) for row in rows],
            limit_reached=any(
                int(row["remaining"]) <= 0
                and not row.get("unlimited")
                for row in rows
                if row["name"] in ("RPM", "TPM")
            ),
            message=(
                "One key for embed/rerank/search/reader. "
                "Free tokens: "
                f"{free_token_grant():,} grant "
                "(operator: 2026-08-25). RPM/TPM card uses "
                "docs embed+rerank caps "
                f"({plan}: "
                f"{lookup_limits(plan)['rpm']} RPM / "
                f"{lookup_limits(plan)['tpm']} TPM). "
                "Search/reader RPM in RATE_LIMITS table."
            ),
        )
