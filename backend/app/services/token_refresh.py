"""Automatic OAuth token refresh service.

Periodically checks all active OAuth provider connections and refreshes
tokens that are about to expire. Runs as a background task in the FastAPI
lifespan.

Ported from: src/sse/services/tokenRefresh.js
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session
from app.models.provider import ProviderConnection
from app.services.oauth import refresh_access_token

logger = logging.getLogger(__name__)

# Refresh tokens within 5 minutes of expiry
TOKEN_EXPIRY_BUFFER_MS = 5 * 60 * 1000  # 5 minutes in milliseconds
TOKEN_EXPIRY_BUFFER = timedelta(milliseconds=TOKEN_EXPIRY_BUFFER_MS)

# How often to check all connections (seconds)
REFRESH_CHECK_INTERVAL = 300  # 5 minutes


def _parse_expires_at(expires_at_str: str) -> datetime | None:
    """Parse an ISO-format expiresAt string to a timezone-aware datetime."""
    if not expires_at_str:
        return None
    try:
        # Handle both "Z" and "+00:00" formats
        dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError) as e:
        logger.warning("Failed to parse expiresAt '%s': %s", expires_at_str, e)
        return None


async def check_and_refresh_tokens() -> dict:
    """Check all active OAuth connections and refresh tokens near expiry.

    Returns a summary dict with refreshed/failed/skipped counts.
    """
    refreshed = 0
    failed = 0
    skipped = 0
    errors = []

    # ── Refresh OAuth tokens ──
    async with async_session() as session:
        stmt = select(ProviderConnection).where(
            ProviderConnection.is_active == True,  # noqa: E712
            ProviderConnection.auth_type == "oauth",
        )
        result = await session.execute(stmt)
        connections = result.scalars().all()

        now = datetime.now(timezone.utc)

        for conn in connections:
            try:
                data = json.loads(conn.data) if conn.data else {}
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Connection %s (%s): invalid data JSON, skipping",
                    conn.id, conn.provider,
                )
                skipped += 1
                continue

            expires_at_str = data.get("expiresAt")
            expires_at = _parse_expires_at(expires_at_str)

            if expires_at is None:
                # No expiry info — skip (likely a non-expiring token or API key)
                skipped += 1
                continue

            remaining = expires_at - now
            if remaining > TOKEN_EXPIRY_BUFFER:
                # Token still valid, not near expiry
                skipped += 1
                continue

            # Token is near expiry or already expired — refresh it
            refresh_token = data.get("refreshToken")
            if not refresh_token:
                logger.warning(
                    "Connection %s (%s): token near expiry but no refreshToken, skipping",
                    conn.id, conn.provider,
                )
                skipped += 1
                continue

            logger.info(
                "Refreshing token for connection %s (%s), remaining=%ds",
                conn.id, conn.provider, int(remaining.total_seconds()),
            )

            try:
                provider_specific_data = data.get("providerSpecificData")
                new_tokens = await refresh_access_token(
                    conn.provider, refresh_token, provider_specific_data,
                )

                # Update data blob with new tokens
                if new_tokens.get("accessToken"):
                    data["accessToken"] = new_tokens["accessToken"]
                if new_tokens.get("refreshToken"):
                    data["refreshToken"] = new_tokens["refreshToken"]
                if new_tokens.get("expiresIn"):
                    # expiresIn is seconds — compute new expiresAt
                    new_expires = now + timedelta(seconds=new_tokens["expiresIn"])
                    data["expiresAt"] = new_expires.isoformat()
                elif new_tokens.get("expiresAt"):
                    data["expiresAt"] = new_tokens["expiresAt"]

                # Merge providerSpecificData if returned
                if new_tokens.get("providerSpecificData"):
                    existing_psd = data.get("providerSpecificData", {})
                    existing_psd.update(new_tokens["providerSpecificData"])
                    data["providerSpecificData"] = existing_psd

                # Clear error fields on success
                data.pop("lastError", None)
                data.pop("lastErrorAt", None)
                data.pop("errorCode", None)

                conn.data = json.dumps(data)
                session.add(conn)
                refreshed += 1

                logger.info(
                    "Token refreshed successfully for connection %s (%s)",
                    conn.id, conn.provider,
                )

            except Exception as e:
                # Mark connection with error info
                data["lastError"] = str(e)
                data["lastErrorAt"] = now.isoformat()
                # Try to extract error code from exception
                error_code = getattr(e, "status_code", None) or getattr(e, "code", None)
                if error_code:
                    data["errorCode"] = str(error_code)

                conn.data = json.dumps(data)
                session.add(conn)
                failed += 1

                logger.error(
                    "Token refresh failed for connection %s (%s): %s",
                    conn.id, conn.provider, e,
                )
                errors.append({
                    "connection_id": str(conn.id),
                    "provider": conn.provider,
                    "error": str(e),
                })

        await session.commit()

    # ── Refresh Qoder tokens (always refresh, not just near expiry) ──
    try:
        from app.providers.qoder.auth import refresh_all_qoder_connections
        qoder_results = await refresh_all_qoder_connections()
        for conn_id, success in qoder_results.items():
            if success:
                refreshed += 1
                logger.info("Qoder background refresh OK: %s", conn_id[:8])
            else:
                failed += 1
                logger.warning("Qoder background refresh FAILED: %s", conn_id[:8])
    except Exception as e:
        logger.error("Qoder background refresh error: %s", e)

    summary = {
        "refreshed": refreshed,
        "failed": failed,
        "skipped": skipped,
        "total": refreshed + failed + skipped,
    }
    if errors:
        summary["errors"] = errors

    return summary


async def token_refresh_loop() -> None:
    """Background loop that periodically refreshes expiring OAuth tokens.

    Runs indefinitely until cancelled. Catches all exceptions to prevent
    the loop from crashing.
    """
    logger.info("Token refresh background task started (interval=%ds)", REFRESH_CHECK_INTERVAL)
    while True:
        try:
            summary = await check_and_refresh_tokens()
            if summary["refreshed"] or summary["failed"]:
                logger.info(
                    "Token refresh cycle: refreshed=%d, failed=%d, skipped=%d",
                    summary["refreshed"], summary["failed"], summary["skipped"],
                )
        except Exception:
            logger.exception("Unexpected error in token refresh cycle")
        await asyncio.sleep(REFRESH_CHECK_INTERVAL)
