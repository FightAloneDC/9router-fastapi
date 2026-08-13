"""Connection health ranking and periodic reachability refresh.

Used by proxy selection (healthy-first) and a background loop that
re-probes connectivity failures so dead hosts stay skipped without
waiting for the next user request.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.services.outbound_proxy import (
    create_upstream_client,
    normalize_upstream_timeout,
    proxy_for_connection,
)

logger = logging.getLogger(__name__)

HEALTHY = "healthy"
RATE_LIMITED = "rate_limited"
EXHAUSTED = "exhausted"
DEAD = "dead"
COOLDOWN = "cooldown"

HEALTH_RANK = {
    HEALTHY: 0,
    RATE_LIMITED: 1,
    COOLDOWN: 2,
    EXHAUSTED: 3,
    DEAD: 4,
}

_EXHAUST_KEYWORDS = (
    "spending", "balance", "exhausted", "quota",
)
_DEAD_KEYWORDS = ("invalid_grant", "revoked")
_CONNECT_HINTS = (
    "connect",
    "timed out",
    "timeout",
    "connection refused",
    "name or service not known",
    "network is unreachable",
    "no route to host",
    "temporary failure in name resolution",
    "all connection attempts failed",
    "nodename nor servname",
)

HEALTH_CHECK_INTERVAL = 60
PROBE_TIMEOUT_SECS = 5.0
STILL_DOWN_COOLDOWN_MS = 60_000


def classify_health(data: dict) -> tuple[str, str | None]:
    """Classify connection health from recorded error state.

    Same tiers as the grok-farm-modular resort contract.
    Returns (status, message).
    """
    error_code = str(data.get("errorCode") or "")
    last_error = str(data.get("lastError") or "").lower()

    if error_code == "401" or any(
        kw in last_error for kw in _DEAD_KEYWORDS
    ):
        return DEAD, (
            "Token expired or revoked — re-authorize the "
            "connection."
        )
    if error_code in ("402", "403") or any(
        kw in last_error for kw in _EXHAUST_KEYWORDS
    ):
        return EXHAUSTED, (
            "Upstream reports no remaining quota "
            "(spending limit)."
        )
    if error_code == "429":
        return RATE_LIMITED, (
            "Rate limited by upstream — in cooldown."
        )
    if error_code or data.get("testStatus") == "unavailable":
        return COOLDOWN, (
            "In cooldown after an upstream error "
            f"(HTTP {error_code or 'unknown'})."
        )
    return HEALTHY, None


def health_rank(data: dict) -> int:
    """Lower rank is preferred. Unknown statuses sort as cooldown."""
    status, _ = classify_health(data)
    return HEALTH_RANK.get(status, HEALTH_RANK[COOLDOWN])


def parse_connection_data(conn: Any) -> dict:
    """Parse a connection JSON blob; empty dict on error."""
    raw = getattr(conn, "data", None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def is_connectivity_failure(data: dict) -> bool:
    """True when the last recorded failure looks like host-down.

    Auth / quota / rate-limit states are not reachability issues
    and must not be cleared by a TCP probe.
    """
    status, _ = classify_health(data)
    if status in (HEALTHY, DEAD, EXHAUSTED, RATE_LIMITED):
        return False
    error_code = str(data.get("errorCode") or "")
    last_error = str(data.get("lastError") or "").lower()
    if error_code == "503":
        return True
    return any(hint in last_error for hint in _CONNECT_HINTS)


def async_session() -> Any:
    """Indirection so tests can stub the DB session factory."""
    from app.database import async_session as _factory
    return _factory()


def _base_url(provider: str, data: dict) -> str:
    from app.services.proxy import _resolve_base_url
    return _resolve_base_url(provider, data)


async def probe_connection(
    db: Any,
    conn: Any,
    data: dict,
) -> bool:
    """Cheap reachability check. Any HTTP response means the host is up."""
    base_url = _base_url(getattr(conn, "provider", ""), data)
    if not base_url:
        return False
    try:
        proxy = await proxy_for_connection(
            db, conn, "testConnection",
        )
    except Exception:
        proxy = None
    timeout = normalize_upstream_timeout(PROBE_TIMEOUT_SECS)
    try:
        async with create_upstream_client(
            proxy=proxy, timeout=timeout,
        ) as client:
            await client.get(base_url)
        return True
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return False
    except httpx.TimeoutException:
        return False
    except httpx.HTTPError:
        return True
    except Exception:
        return False


def _mark_recovered(data: dict) -> None:
    from app.services.proxy import build_clear_cooldown_update

    data.update(build_clear_cooldown_update())
    data["testStatus"] = "active"
    data["errorCode"] = None
    data["lastError"] = None
    data["lastErrorAt"] = None


def _mark_still_down(data: dict) -> None:
    until = datetime.now(timezone.utc) + timedelta(
        milliseconds=STILL_DOWN_COOLDOWN_MS,
    )
    data["rateLimitedUntil"] = until.isoformat()
    data["testStatus"] = "unavailable"


async def refresh_connection_health() -> dict:
    """Re-probe connectivity-failed connections and update blobs."""
    probed = 0
    recovered = 0
    still_down = 0
    skipped = 0

    from sqlalchemy import select

    from app.models.provider import ProviderConnection

    async with async_session() as session:
        result = await session.execute(
            select(ProviderConnection).where(
                ProviderConnection.is_active == True,  # noqa: E712
            )
        )
        connections = list(result.scalars().all())
        dirty_providers: set[str] = set()

        for conn in connections:
            data = parse_connection_data(conn)
            if not is_connectivity_failure(data):
                skipped += 1
                continue
            ok = await probe_connection(session, conn, data)
            probed += 1
            if ok:
                _mark_recovered(data)
                recovered += 1
            else:
                _mark_still_down(data)
                still_down += 1
            conn.data = json.dumps(data)
            session.add(conn)
            dirty_providers.add(conn.provider)

        if probed:
            await session.commit()
            from app.services.proxy import (
                invalidate_connection_cache,
            )
            for provider_id in dirty_providers:
                invalidate_connection_cache(provider_id)

    return {
        "probed": probed,
        "recovered": recovered,
        "still_down": still_down,
        "skipped": skipped,
        "total": probed + skipped,
    }


async def connection_health_loop() -> None:
    """Background loop: probe dead hosts every HEALTH_CHECK_INTERVAL."""
    logger.info(
        "Connection health refresh started (interval=%ds)",
        HEALTH_CHECK_INTERVAL,
    )
    while True:
        try:
            summary = await refresh_connection_health()
            if summary["probed"]:
                logger.info(
                    "Connection health cycle: "
                    "probed=%d recovered=%d still_down=%d",
                    summary["probed"],
                    summary["recovered"],
                    summary["still_down"],
                )
        except Exception:
            logger.exception(
                "Unexpected error in connection health cycle",
            )
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
