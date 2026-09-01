"""Qoder usage handler.

Endpoint: QODER_QUOTA_USAGE_URL (providers/qoder/constants.py)
Auth: OAuth Bearer token (not COSY).

Published trial cap: QoderConfig.RATE_LIMITS["trial"]
(credits + days). Live used/remaining/expiresAt come from the
quota API. Response shape (verified 2026-08):

  {"userType": "personal_professional_trial",
   "usageType": "credits",
   "isQuotaExceeded": true,
   "expiresAt": 1787423063188,
   "userQuota": {"total": 300.0, "used": 300.0,
                 "remaining": 0.0, "percentage": 1.0,
                 "unit": "credits"}, ...}
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import async_session
from app.models.usage import UsageHistory
from app.providers.qoder.bulk import parse_expires_at
from app.providers.qoder.config import QoderConfig
from app.providers.qoder.constants import (
    QODER_QUOTA_USAGE_URL,
)
from app.services.proxy import invalidate_connection_cache

from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)


def published_credit_cap() -> int:
    """Trial credit total from RATE_LIMITS (Provider Detail table)."""
    table = QoderConfig().RATE_LIMITS
    return int(table.get("trial", {}).get("credits") or 300)


def as_credit(value: Any, default: float = 0.0) -> float:
    """Parse a credit field. Never int() or round."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def credits_from_tokens(raw: dict | str | None) -> float:
    """Credits charged on one chat (SSE ``usage`` / usage_history).

    Return the full float. Never int() or round.
    """
    if raw is None:
        return 0.0
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return 0.0
    elif isinstance(raw, dict):
        data = raw
    else:
        return 0.0
    val = data.get("credits")
    if val is None:
        val = data.get("original_credits")
    try:
        return max(0.0, float(val))
    except (TypeError, ValueError):
        return 0.0


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


async def local_credits(connection_id: str | None) -> float:
    """Sum ``usage_history.tokens.credits`` for this connection."""
    cid = _cid_key(connection_id)
    if not cid:
        return 0.0
    stored = func.replace(
        func.lower(func.coalesce(UsageHistory.connection_id, "")),
        "-",
        "",
    )
    async with async_session() as db:
        rows = (
            await db.execute(
                select(UsageHistory.tokens).where(
                    func.lower(UsageHistory.provider) == "qoder",
                    stored == cid,
                )
            )
        ).all()
    total = 0.0
    for (raw,) in rows:
        total += credits_from_tokens(raw)
    return total


async def latest_chat_credits(connection_id: str | None) -> float:
    """Credits on the newest usage_history row for this connection."""
    cid = _cid_key(connection_id)
    if not cid:
        return 0.0
    stored = func.replace(
        func.lower(func.coalesce(UsageHistory.connection_id, "")),
        "-",
        "",
    )
    async with async_session() as db:
        row = (
            await db.execute(
                select(UsageHistory.tokens).where(
                    func.lower(UsageHistory.provider) == "qoder",
                    stored == cid,
                ).order_by(
                    UsageHistory.timestamp.desc(),
                ).limit(1)
            )
        ).first()
    if row is None:
        return 0.0
    return credits_from_tokens(row[0])


def usage_from_api(
    data: dict,
    blob: dict | None = None,
) -> UsageResponse:
    """Map a live quota/usage JSON body to UsageResponse."""
    extra = blob or {}
    quota = data.get("userQuota") or {}
    total = as_credit(quota.get("total")) or float(
        published_credit_cap()
    )
    used = as_credit(quota.get("used"))
    remaining = quota.get("remaining")
    if remaining is None:
        remaining = max(0.0, total - used)
    else:
        remaining = as_credit(remaining)
    unit = (quota.get("unit") or "credits").title()
    reset_at = None
    expires_ms = data.get("expiresAt")
    if isinstance(expires_ms, (int, float)) and expires_ms > 0:
        reset_at = datetime.fromtimestamp(
            expires_ms / 1000, tz=timezone.utc,
        ).isoformat()
    if reset_at is None:
        reset_at = parse_expires_at(extra.get("proTrialEndAt"))
    return UsageResponse(
        plan=data.get("userType") or extra.get("userType"),
        quotas=[QuotaItem(
            name=unit,
            used=used,
            total=total,
            remaining=remaining,
            remaining_percentage=QoderUsageHandler._pct(
                used, total,
            ),
            reset_at=reset_at,
        )],
        limit_reached=bool(data.get("isQuotaExceeded"))
        or remaining <= 0,
    )


def usage_from_stored(data: dict) -> UsageResponse | None:
    """Last stored quota/trial check on the connection, if any.

    Blob ``expiresAt`` is job-token TTL, not trial end — do
    not read it here. Trial window is ``proTrialEndAt``.
    """
    total = data.get("farmQuotaTotal")
    remaining = data.get("farmQuotaRemaining")
    exceeded = data.get("farmQuotaExceeded")
    reset_at = parse_expires_at(data.get("proTrialEndAt"))
    has_credits = (
        total is not None
        or remaining is not None
        or exceeded is not None
    )
    if not has_credits and reset_at is None:
        return None
    plan = data.get("userType") or data.get("plan")
    plan_s = str(plan) if plan else None
    if not has_credits:
        return UsageResponse(
            plan=plan_s,
            quotas=[QuotaItem(
                name="Credits",
                reset_at=reset_at,
            )],
        )
    cap = (
        as_credit(total)
        if total is not None
        else float(published_credit_cap())
    )
    if remaining is not None:
        left = as_credit(remaining)
        used = max(0.0, cap - left)
    elif exceeded is True:
        left = 0
        used = cap
    else:
        used = 0
        left = cap
    hit = bool(exceeded) if exceeded is not None else left <= 0
    return UsageResponse(
        plan=plan_s,
        quotas=[QuotaItem(
            name="Credits",
            used=used,
            total=cap,
            remaining=left,
            remaining_percentage=QoderUsageHandler._pct(used, cap),
            reset_at=reset_at,
        )],
        limit_reached=hit,
    )


def apply_local_used(
    result: UsageResponse,
    local_used: float,
) -> UsageResponse:
    """Raise used to chat-log credits when they exceed API used."""
    if local_used <= 0:
        return result
    cap = float(published_credit_cap())
    if not result.quotas:
        left = max(0.0, cap - local_used)
        result.quotas = [QuotaItem(
            name="Credits",
            used=local_used,
            total=cap,
            remaining=left,
            remaining_percentage=QoderUsageHandler._pct(
                local_used, cap,
            ),
        )]
        result.limit_reached = left <= 0
        return result
    item = result.quotas[0]
    used = max(item.used, local_used)
    if used == item.used:
        return result
    total = item.total or cap
    left = max(0.0, total - used)
    result.quotas[0] = item.model_copy(update={
        "used": used,
        "remaining": left,
        "remaining_percentage": QoderUsageHandler._pct(
            used, total,
        ),
    })
    result.limit_reached = result.limit_reached or left <= 0
    return result


def _reset_at_past(value: str | None, now: datetime) -> bool:
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00"),
        )
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt <= now


def live_bar_is_spent(
    result: UsageResponse,
    *,
    now: datetime | None = None,
) -> bool:
    """True when a live credit bar is exhausted or trial-ended."""
    now = now or datetime.now(timezone.utc)
    if result.limit_reached:
        return True
    for item in result.quotas:
        if (
            item.total > 0
            and item.remaining is not None
            and item.remaining <= 0
        ):
            return True
        if _reset_at_past(item.reset_at, now):
            return True
    return False


async def retire_if_spent(
    db: Any,
    connection_id: str | None,
    result: UsageResponse,
    *,
    now: datetime | None = None,
) -> bool:
    """Set is_active=False when the live bar is spent. No-op else."""
    if not connection_id:
        return False
    if not live_bar_is_spent(result, now=now):
        return False
    try:
        cid = uuid.UUID(connection_id)
    except (TypeError, ValueError):
        return False
    from app.models.provider import ProviderConnection

    conn = await db.get(ProviderConnection, cid)
    if conn is None or not conn.is_active:
        return False
    conn.is_active = False
    invalidate_connection_cache(conn.provider)
    logger.info(
        "Qoder connection %s retired (spent or trial ended)",
        connection_id[:8],
    )
    return True


async def _retire_live_fetch(
    connection_id: str | None,
    result: UsageResponse,
) -> None:
    if not connection_id:
        return
    async with async_session() as db:
        changed = await retire_if_spent(
            db, connection_id, result,
        )
        if changed:
            await db.commit()


def _blob_from_conn(conn: Any) -> dict[str, Any]:
    if conn is None:
        return {}
    raw = getattr(conn, "data", None)
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _farm_has_credits(blob: dict[str, Any]) -> bool:
    return (
        blob.get("farmQuotaTotal") is not None
        or blob.get("farmQuotaRemaining") is not None
        or blob.get("farmQuotaExceeded") is not None
    )


def _cache_credit_row(cache: Any) -> dict[str, Any] | None:
    if cache is None or not cache.quotas:
        return None
    try:
        rows = json.loads(cache.quotas)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(rows, list) or not rows:
        return None
    row0 = rows[0]
    return row0 if isinstance(row0, dict) else None


async def _write_observe_bar(
    db: Any,
    cid: uuid.UUID,
    cache: Any,
    *,
    used: float,
    total: float,
    plan: str | None,
    reset_at: str | None,
    name: str = "Credits",
    limit_reached: bool | None = None,
    live: bool = False,
) -> None:
    left = max(0.0, float(total) - used)
    hit = (
        bool(limit_reached) or left <= 0
        if limit_reached is not None
        else left <= 0
    )
    result = UsageResponse(
        plan=plan,
        quotas=[QuotaItem(
            name=name,
            used=used,
            total=total,
            remaining=left,
            remaining_percentage=QoderUsageHandler._pct(
                used, total,
            ),
            reset_at=reset_at,
        )],
        limit_reached=hit,
    )
    await _write_observe_bar_from_result(
        db, cid, cache, result, live=live,
    )


async def _write_observe_bar_from_result(
    db: Any,
    cid: uuid.UUID,
    cache: Any,
    result: UsageResponse,
    *,
    live: bool = False,
) -> None:
    from app.models.quota_cache import QuotaCache

    if cache is None:
        cache = QuotaCache(connection_id=cid)
        db.add(cache)
    cache.plan = result.plan
    cache.quotas = json.dumps(
        [q.model_dump() for q in result.quotas]
    )
    cache.limit_reached = result.limit_reached
    cache.fetched_at = datetime.now(timezone.utc)
    if live:
        await retire_if_spent(db, str(cid), result)
    await db.commit()


async def sync_quota_after_token_refresh(
    db: Any,
    connection_id: str,
    access_token: str,
    provider_data: dict | None = None,
) -> None:
    """GET quota/usage after a real job-token refresh. Fail-open.

    Writes ``quota_cache`` only when the GET succeeds. Uses
    max(API used, local credits). Does not run on skipped
    still-fresh refresh cycles.
    """
    if not access_token:
        return
    try:
        cid = uuid.UUID(connection_id)
    except (TypeError, ValueError):
        return
    blob = provider_data or {}
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    handler = QoderUsageHandler()
    try:
        resp = await handler._get(
            QODER_QUOTA_USAGE_URL, headers,
        )
    except Exception as e:
        logger.warning("Qoder refresh usage GET failed: %s", e)
        return
    if resp.status_code != 200:
        logger.warning(
            "Qoder refresh usage GET status %s",
            resp.status_code,
        )
        return
    data = resp.json()
    if not isinstance(data, dict):
        return
    local_used = await local_credits(connection_id)
    result = apply_local_used(
        usage_from_api(data, blob), local_used,
    )
    if not result.quotas:
        return
    from app.models.quota_cache import QuotaCache

    cache = await db.get(QuotaCache, cid)
    await _write_observe_bar_from_result(
        db, cid, cache, result, live=True,
    )


class QoderUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "qoder"
    # True: GET /quota serves quota_cache (chat observe_complete
    # already wrote it). fetch() still GETs quota/usage on
    # GET /usage/{id} (15 min cache / force).
    USES_UPSTREAM = True

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        blob = provider_data or {}
        stored = usage_from_stored(blob)
        local_used = await local_credits(connection_id)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        try:
            resp = await self._get(QODER_QUOTA_USAGE_URL, headers)
        except Exception as e:
            logger.warning("Qoder usage fetch failed: %s", e)
            if stored is not None:
                return apply_local_used(stored, local_used)
            if local_used:
                return apply_local_used(UsageResponse(), local_used)
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code != 200:
            if stored is not None:
                return apply_local_used(stored, local_used)
            if local_used:
                return apply_local_used(UsageResponse(), local_used)
            return UsageResponse(
                message=(
                    f"Qoder API returned {resp.status_code}"
                )
            )

        data = resp.json()
        if not isinstance(data, dict):
            if stored is not None:
                return apply_local_used(stored, local_used)
            if local_used:
                return apply_local_used(UsageResponse(), local_used)
            return UsageResponse(
                message="Qoder API returned invalid JSON"
            )
        result = usage_from_api(data, blob)
        result = apply_local_used(result, local_used)
        await _retire_live_fetch(connection_id, result)
        return result

    async def observe_complete(
        self,
        db: Any,
        connection_id: str,
    ) -> None:
        """After a proxied chat, add this chat's credits to a floor.

        Floor: existing quota_cache, else farmQuota*, else one
        GET quota/usage. Never replace a vendor bar with the
        9router sum. Never GET on every chat.
        """
        from app.models.provider import ProviderConnection
        from app.models.quota_cache import QuotaCache

        latest = await latest_chat_credits(connection_id)
        if latest <= 0:
            return
        try:
            cid = uuid.UUID(connection_id)
        except (TypeError, ValueError):
            return
        cache = await db.get(QuotaCache, cid)
        row = _cache_credit_row(cache)
        if row is not None:
            cap = as_credit(
                row.get("total") or published_credit_cap(),
            ) or float(published_credit_cap())
            used = as_credit(row.get("used")) + latest
            raw_reset = row.get("reset_at")
            reset_at = (
                raw_reset if isinstance(raw_reset, str) else None
            )
            await _write_observe_bar(
                db, cid, cache,
                used=used,
                total=cap,
                plan=cache.plan,
                reset_at=reset_at,
                name=str(row.get("name") or "Credits"),
                live=True,
            )
            return

        conn = await db.get(ProviderConnection, cid)
        blob = _blob_from_conn(conn)
        if _farm_has_credits(blob):
            stored = usage_from_stored(blob)
            item = (
                stored.quotas[0]
                if stored is not None and stored.quotas
                else None
            )
            if item is not None:
                cap = float(
                    item.total or published_credit_cap()
                )
                used = as_credit(item.used) + latest
                await _write_observe_bar(
                    db, cid, None,
                    used=used,
                    total=cap,
                    plan=stored.plan,
                    reset_at=item.reset_at,
                    name=item.name or "Credits",
                )
                return

        token = (
            blob.get("accessToken")
            or blob.get("apiKey")
            or ""
        )
        if not token:
            return
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        try:
            resp = await self._get(
                QODER_QUOTA_USAGE_URL, headers,
            )
        except Exception as e:
            logger.warning(
                "Qoder observe usage GET failed: %s", e,
            )
            return
        if resp.status_code != 200:
            logger.warning(
                "Qoder observe usage GET status %s",
                resp.status_code,
            )
            return
        data = resp.json()
        if not isinstance(data, dict):
            return
        local_used = await local_credits(connection_id)
        result = apply_local_used(
            usage_from_api(data, blob), local_used,
        )
        await _write_observe_bar_from_result(
            db, cid, None, result, live=True,
        )
