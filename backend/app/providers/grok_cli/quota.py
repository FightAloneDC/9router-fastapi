"""Grok CLI (Grok Build) usage handler (quota tracker hook).

Local-state handler (``USES_UPSTREAM = False``): xAI exposes no
balance API for free-tier accounts. Quota data is assembled from
three local sources instead:

1. Local token accumulation — the daily "used" counter is the
   sum of today's (UTC) prompt+completion tokens from
   usage_history (written by the proxy per request). This is
   the only usage signal that actually moves: the upstream
   X-Ratelimit-Remaining-* headers arrive static (always full)
   and are not trusted for usage (observed 2026-08).

2. Upstream rate-limit headers — every successful chat answers
   with counters (observed 2026-08):

       X-Ratelimit-Limit-Tokens: 1000000
       X-Ratelimit-Remaining-Tokens: ...   (static, ignored)
       X-Ratelimit-Limit-Requests: 21
       X-Ratelimit-Remaining-Requests: ...

   The proxy dispatches response headers to observe_response(),
   which snapshots them into the quota_cache table. fetch()
   uses the snapshot for the account's token LIMIT and the
   requests-counter row only.

3. Recorded upstream errors — the proxy cooldown path stores
   errorCode / lastError / testStatus on the connection data
   blob; classified with the grok-farm-modular resort contract
   (cli/nine_router/health.py): 429 → rate-limited; 402/403 or
   "spending"/"balance"/"exhausted"/"quota" keywords →
   exhausted; 401 / invalid_grant / revoked → dead. The
   free-usage 429 body carries authoritative numbers —
   "tokens (actual/limit): 539793/500000" — which calibrate
   both used and limit for that connection.

Research notes (grok-farm-modular, verified 2026-08):
- The free tier comes from x.ai and is limited to grok-4.5.
  Grok (grok.com) has no free plan — grok-build 402s on free
  accounts by design (model gating, not exhaustion).
- Daily free allowance is account-random: **1M or 500K**
  tokens/day. Published both rows on
  ``GrokCliConfig.RATE_LIMITS`` (``free/1m``, ``free/500k``)
  with ``requests: 21``. Headers often claim 1M; 429 body may
  show 500K — the 429 body is authoritative when present.
- Enforcement observed 2026-08-09: one farmed account 429'd at
  an actual 500K limit (rolling 24h window) while its headers
  still claimed 1M.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import async_session
from app.models.quota_cache import QuotaCache
from app.models.usage import UsageHistory
from app.providers.grok_cli.config import GrokCliConfig
from app.services.connection_health import (
    COOLDOWN as COOLDOWN,
)
from app.services.connection_health import (
    DEAD as DEAD,
)
from app.services.connection_health import (
    EXHAUSTED as EXHAUSTED,
)
from app.services.connection_health import (
    HEALTHY as HEALTHY,
)
from app.services.connection_health import (
    RATE_LIMITED as RATE_LIMITED,
)
from app.services.connection_health import (
    classify_health as classify_health,
)
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)


def published_daily_tokens_1m() -> int:
    """Default free daily cap (1M tier) from RATE_LIMITS."""
    table = GrokCliConfig().RATE_LIMITS
    return int(table.get("free/1m", {}).get("tpd") or 1_000_000)


def published_daily_tokens_500k() -> int:
    """Alternate free daily cap (500K tier) from RATE_LIMITS."""
    table = GrokCliConfig().RATE_LIMITS
    return int(table.get("free/500k", {}).get("tpd") or 500_000)


def published_request_cap() -> int:
    """Published Limit-Requests from RATE_LIMITS (both tiers)."""
    table = GrokCliConfig().RATE_LIMITS
    row = table.get("free/1m") or table.get("free/500k") or {}
    return int(row.get("requests") or 21)


# Free-tier daily token allowance default (1M tier). Account may
# instead be on the 500K tier — see RATE_LIMITS free/500k.
GROK_CLI_FREE_DAILY_TOKENS = published_daily_tokens_1m()

_LIMIT_TOKENS_HDR = "x-ratelimit-limit-tokens"
_REMAIN_TOKENS_HDR = "x-ratelimit-remaining-tokens"
_LIMIT_REQ_HDR = "x-ratelimit-limit-requests"
_REMAIN_REQ_HDR = "x-ratelimit-remaining-requests"

# JWT access-token tier claim → display plan
_TIER_PLANS = {
    0: "Free",
    1: "SuperGrok",
    2: "X Basic",
    3: "X Premium",
    4: "X Premium Plus",
    5: "SuperGrok Heavy",
    6: "SuperGrok Lite",
}

def _plan_from_access_token(access_token: str) -> str:
    """Display-only plan from the JWT tier claim."""
    try:
        payload_b64 = access_token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(payload_b64)
        )
        return _TIER_PLANS.get(payload.get("tier"), "")
    except Exception:
        return ""


def _today_utc_midnight() -> datetime:
    """The daily allowance window resets at UTC midnight."""
    return datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )


def _next_reset_iso() -> str:
    return (
        _today_utc_midnight() + timedelta(days=1)
    ).isoformat()


def _hdr_int(
    headers: Any, key: str,
) -> int | None:
    """Case-insensitive header lookup parsed as int."""
    raw = headers.get(key)
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


# "tokens (actual/limit): 539793/500000" in the free-usage 429
_EXHAUST_TOKENS_RE = re.compile(
    r"tokens \(actual/limit\):\s*(\d+)\s*/\s*(\d+)"
)


def _parse_exhausted_tokens(
    last_error: str,
) -> tuple[int | None, int | None]:
    """Extract authoritative used/limit from a recorded
    free-usage-exhausted 429 body."""
    match = _EXHAUST_TOKENS_RE.search(last_error or "")
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _quota_dict(
    name: str, used: int, total: int,
) -> dict:
    remaining = max(0, total - used)
    return {
        "name": name,
        "used": min(used, total),
        "total": total,
        "remaining": remaining,
        "remaining_percentage": (
            100.0 if total <= 0
            else max(0.0, remaining / total * 100)
        ),
        "reset_at": _next_reset_iso(),
        "unlimited": False,
    }


class GrokCliUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "grok-cli"
    USES_UPSTREAM = False

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        """Snapshot upstream rate-limit headers into
        quota_cache (authoritative daily counters)."""
        limit = _hdr_int(headers, _LIMIT_TOKENS_HDR)
        remaining = _hdr_int(headers, _REMAIN_TOKENS_HDR)
        if limit is None or remaining is None:
            return  # not a rate-limited upstream response

        # Token "remaining" headers are static on free tier (always
        # full) — do not trust them for used. Accumulate from local
        # usage_history instead.
        used = await self._today_token_usage(connection_id)

        quotas = [_quota_dict(
            "Daily free (grok-4.5)",
            used=used,
            total=limit,
        )]

        req_limit = _hdr_int(headers, _LIMIT_REQ_HDR)
        req_remaining = _hdr_int(headers, _REMAIN_REQ_HDR)
        if req_limit is not None and req_remaining is not None:
            quotas.append(_quota_dict(
                "Requests",
                used=max(0, req_limit - req_remaining),
                total=req_limit,
            ))

        cache = await db.get(
            QuotaCache, uuid.UUID(connection_id),
        )
        if cache is None:
            cache = QuotaCache(
                connection_id=uuid.UUID(connection_id),
            )
            db.add(cache)
        cache.quotas = json.dumps(quotas)
        cache.limit_reached = used >= limit
        cache.fetched_at = datetime.now(timezone.utc)
        await db.commit()

    async def _today_token_usage(
        self, connection_id: str,
    ) -> int:
        """Primary usage source: sum today's (UTC)
        prompt+completion tokens from usage_history (written by
        the proxy per request)."""
        async with self._session() as db:
            result = await db.execute(
                select(func.coalesce(func.sum(
                    UsageHistory.prompt_tokens
                    + UsageHistory.completion_tokens
                ), 0)).where(
                    UsageHistory.connection_id
                    == connection_id
                ).where(
                    UsageHistory.timestamp
                    >= _today_utc_midnight()
                )
            )
            return int(result.scalar() or 0)

    async def _today_snapshot(
        self, connection_id: str,
    ) -> tuple[list[dict], bool] | None:
        """Return today's header snapshot (quotas, limit_reached)
        stored in quota_cache, or None when absent/stale."""
        async with self._session() as db:
            cache = await db.get(
                QuotaCache, uuid.UUID(connection_id),
            )
        if cache is None or not cache.quotas:
            return None
        fetched_at = cache.fetched_at
        if fetched_at is not None:
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(
                    tzinfo=timezone.utc,
                )
            if fetched_at < _today_utc_midnight():
                return None  # window already reset
        try:
            quotas = json.loads(cache.quotas)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(quotas, list):
            return None
        return quotas, bool(cache.limit_reached)

    @staticmethod
    def _session():
        return async_session()

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        data = provider_data or {}
        plan = (
            _plan_from_access_token(
                data.get("accessToken") or access_token
            )
            or "Free"
        )
        status, message = classify_health(data)

        # Header snapshot (today): account token LIMIT + the
        # requests-counter row. Its usage counters arrive static
        # from the upstream, so "used" is accumulated locally.
        token_total = GROK_CLI_FREE_DAILY_TOKENS
        req_quota: dict | None = None
        if connection_id:
            snapshot = await self._today_snapshot(
                connection_id
            )
            if snapshot is not None:
                for q in snapshot[0]:
                    if not isinstance(q, dict):
                        continue
                    name = str(q.get("name", ""))
                    total = q.get("total")
                    if name.startswith("Daily free") and total:
                        token_total = int(total)
                    elif name == "Requests":
                        req_quota = q

        # Locally accumulated token usage for today (UTC)
        used = 0
        if connection_id:
            used = await self._today_token_usage(
                connection_id
            )

        # Authoritative calibration from a recorded exhaustion
        # 429: "... tokens (actual/limit): 539793/500000 ..."
        actual, limit = _parse_exhausted_tokens(
            str(data.get("lastError") or "")
        )
        if actual is not None:
            used = max(used, actual)
            if limit:
                token_total = limit

        quotas: list[QuotaItem] = [QuotaItem(**_quota_dict(
            "Daily free (grok-4.5)", used, token_total,
        ))]
        if req_quota is not None:
            quotas.append(QuotaItem(**req_quota))
        limit_reached = used >= token_total

        # Hard error signals override the counters
        if status in (EXHAUSTED, DEAD):
            limit_reached = True
            for q in quotas:
                q.used = q.total
                q.remaining = 0
                q.remaining_percentage = 0.0

        return UsageResponse(
            plan=plan,
            quotas=quotas,
            message=message,
            limit_reached=limit_reached,
        )
