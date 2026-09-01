"""Qoder authentication: device flow + PAT import + token refresh.

⚠️  CRITICAL: Do NOT modify this provider without user approval.
    Extensive investigation and trial-error has been done.
    See docs/archives/qoder-docs/BUG-FIXING-LOG.md before making any changes.

Device Flow:
  1. Generate a PKCE pair locally and a fresh nonce + machine id.
  2. Open https://qoder.com/device/selectAccounts?challenge=...&nonce=...
     in the user's browser.
  3. Poll openapi.qoder.sh/api/v1/deviceToken/poll until the user authorizes
     and the upstream returns a `dt-...` access token.

PAT Import:
  1. User provides Personal Access Token (pt-xxx) from qoder.com/account/integrations
  2. Exchange PAT for regular token via /api/v1/jobToken/exchange
  3. Fetch user info with the regular token
  4. Store regular token for COSY signing

Token Refresh:
  PAT-exchanged job tokens (jt-xxx) expire in ~24 hours and come with
  a jrt-* refresh token. OAuth / device flow comes with a drt-* refresh
  token. Both prefixes work on POST /api/v1/jobToken/refresh
  (openapi.qoder.sh). The old endpoint on center.qoder.sh returns 403.
  Background refresh_all only POSTs near expiresAt (1h buffer) or when
  expiresAt is missing. On-demand try_refresh_connection still handles
  401/403.
"""

import base64
import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app import database
from app.models.provider import ProviderConnection
from app.services import proxy as proxy_service
from app.services.outbound_proxy import (
    create_upstream_client,
    proxy_for_connection,
    use_outbound_proxy,
)

from .constants import (
    QODER_DEVICE_TOKEN_URL,
    QODER_JOB_TOKEN_REFRESH_BUFFER_S,
    QODER_LOGIN_URL,
    QODER_OPENAPI_BASE,
    QODER_REFRESH_TOKEN_URL,
    QODER_USERINFO_URL,
)

logger = logging.getLogger(__name__)

# Values larger than this are treated as milliseconds (Qoder jobToken
# returns expires_in=86400000 for 24h). Below → already seconds.
_EXPIRES_IN_MS_THRESHOLD = 10_000_000


def expires_in_to_seconds(expires_in: object) -> int | None:
    """Normalize Qoder expires_in (seconds or ms) to seconds."""
    if expires_in is None:
        return None
    try:
        value = int(expires_in)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value > _EXPIRES_IN_MS_THRESHOLD:
        return value // 1000
    return value


def _parse_job_expires_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00"),
        )
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def job_token_needs_refresh(
    data: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """True when the background loop should hit jobToken/refresh.

    Missing expiresAt (legacy blobs) refreshes once so expiry is
    written. Fresh tokens wait until within the 1h buffer.
    """
    now = now or datetime.now(timezone.utc)
    expires_at = _parse_job_expires_at(data.get("expiresAt"))
    if expires_at is None:
        return True
    remaining = expires_at - now
    return remaining <= timedelta(
        seconds=QODER_JOB_TOKEN_REFRESH_BUFFER_S,
    )


def apply_qoder_token_expiry(
    data: dict[str, Any],
    new_tokens: dict[str, Any],
    *,
    now: datetime | None = None,
) -> None:
    """Write expiresAt / refreshTokenExpiresAt after a successful refresh.

    Prefer absolute timestamps from upstream; otherwise derive from
    expires_in / refresh_token_expires_in (ms or seconds).
    """
    now = now or datetime.now(timezone.utc)

    expires_at = (
        new_tokens.get("expires_at")
        or new_tokens.get("expiresAt")
    )
    if isinstance(expires_at, str) and expires_at.strip():
        data["expiresAt"] = expires_at.strip()
    else:
        seconds = expires_in_to_seconds(new_tokens.get("expires_in"))
        if seconds is not None:
            data["expiresAt"] = (
                now + timedelta(seconds=seconds)
            ).isoformat()

    refresh_exp = (
        new_tokens.get("refresh_token_expires_at")
        or new_tokens.get("refreshTokenExpiresAt")
    )
    if isinstance(refresh_exp, str) and refresh_exp.strip():
        data["refreshTokenExpiresAt"] = refresh_exp.strip()
    else:
        refresh_seconds = expires_in_to_seconds(
            new_tokens.get("refresh_token_expires_in"),
        )
        if refresh_seconds is not None:
            data["refreshTokenExpiresAt"] = (
                now + timedelta(seconds=refresh_seconds)
            ).isoformat()


def _base64url(data: bytes) -> str:
    """Encode bytes to base64url (no padding)."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE verifier + S256 challenge pair.

    Uses 32 random bytes (matches qodercli/Veria).

    Returns:
        (verifier, challenge) as base64url strings
    """
    verifier = _base64url(secrets.token_bytes(32))
    challenge = _base64url(hashlib.sha256(verifier.encode('ascii')).digest())
    return verifier, challenge


def initiate_device_flow() -> dict[str, str]:
    """Initiate the device flow.

    Returns:
        Dict with verification_uri_complete, code_verifier, nonce, machine_id
    """
    verifier, challenge = generate_pkce_pair()
    nonce = str(uuid.uuid4())
    machine_id = str(uuid.uuid4())

    params = {
        "challenge": challenge,
        "challenge_method": "S256",
        "machine_id": machine_id,
        "nonce": nonce,
    }

    # Build URL manually to avoid encoding issues
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    verification_uri_complete = f"{QODER_LOGIN_URL}?{param_str}"

    return {
        "verification_uri_complete": verification_uri_complete,
        "code_verifier": verifier,
        "nonce": nonce,
        "machine_id": machine_id,
    }


async def poll_device_token(
    nonce: str,
    code_verifier: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Single poll attempt for device token.

    Args:
        nonce: Device nonce from initiate_device_flow
        code_verifier: PKCE verifier from initiate_device_flow
        timeout: Request timeout in seconds

    Returns:
        Dict with status: "pending" or "ok" with token data
        Raises Exception on terminal failure
    """
    if not nonce or not code_verifier:
        raise ValueError("poll_device_token: missing nonce or code verifier")

    url = f"{QODER_DEVICE_TOKEN_URL}?nonce={nonce}&verifier={code_verifier}&challenge_method=S256"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Go-http-client/2.0",
            },
        )

    # Pending — server has registered the device code but the user hasn't
    # finished the browser flow yet. Both 202 and 404 mean "keep polling".
    if response.status_code in (202, 404):
        return {"status": "pending"}

    text = response.text

    if response.status_code != 200:
        message = f"Qoder device token poll failed: HTTP {response.status_code}"
        try:
            body = response.json()
            if body.get("message"):
                message = f"Qoder device token poll failed: {body['message']}"
        except Exception:
            pass
        raise Exception(message)

    # Success — parse token data
    try:
        data = response.json()
    except Exception:
        raise Exception(f"Qoder device token poll: invalid JSON response")

    # Qoder returns 'token' (not 'accessToken' or 'access_token')
    access_token = data.get("token") or data.get("accessToken") or data.get("access_token")
    if not access_token:
        raise Exception("Qoder device token poll: no token in response")

    # Calculate expiry (matching Node.js parseExpiry logic)
    expires_at = data.get("expires_at")
    expires_in = data.get("expires_in")
    
    # If expires_at is a timestamp (ms), calculate remaining seconds
    if expires_at and isinstance(expires_at, (int, float)):
        remaining_seconds = max(0, int((expires_at - __import__('time').time() * 1000) / 1000))
        expires_in = max(24 * 60 * 60, remaining_seconds)  # Minimum 1 day
    elif expires_in is None:
        expires_in = 30 * 24 * 60 * 60  # Default 30 days

    return {
        "status": "ok",
        "access_token": access_token,
        "refresh_token": data.get("refresh_token"),
        "expires_in": expires_in,
        "token_type": data.get("token_type", "Bearer"),
        "scope": data.get("scope"),
        "user_id": data.get("user_id"),
        "display_name": data.get("display_name"),
        "email": data.get("email"),
    }


async def fetch_user_info(access_token: str, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch user info from Qoder API.

    Args:
        access_token: Access token (from device flow or PAT exchange)
        timeout: Request timeout in seconds

    Returns:
        Dict with user info
    """
    logger = logging.getLogger(__name__)

    # Try multiple header formats (qodercli uses Bearer)
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    async with create_upstream_client(timeout=timeout) as client:
        # First try with Authorization header
        response = await client.get(
            QODER_USERINFO_URL,
            headers=headers,
        )

        # If that fails, try with query parameter
        if response.status_code != 200:
            logger.debug(f"Bearer auth failed ({response.status_code}), trying query param")
            response = await client.get(
                f"{QODER_USERINFO_URL}?accessToken={access_token}",
                headers={"Accept": "application/json"},
            )

    if response.status_code != 200:
        raise Exception(f"Failed to fetch user info: HTTP {response.status_code}")

    result = response.json()
    logger.info(f"Qoder userinfo response keys: {list(result.keys())}")

    # Handle different response formats
    if result.get("success") is not None:
        # Standard format with success field
        if not result.get("success"):
            raise Exception(f"User info request failed: {result.get('message', 'Unknown error')}")
        return result.get("data", {})

    # Direct format (no success field) - check for known user fields
    # Qoder returns 'id' not 'userId' or 'uid'
    if result.get("id") or result.get("uid") or result.get("userId"):
        return result

    # If response has any keys, return it as-is (might be flat structure)
    if result:
        logger.warning(f"Unexpected userinfo format, returning as-is: {list(result.keys())}")
        return result

    raise Exception("Unexpected user info response format")


async def exchange_personal_token(
    personal_token: str,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Exchange a Personal Access Token (PAT) for a regular token.

    The PAT (pt-xxx) cannot be used directly for COSY-signed requests.
    It must be exchanged for a regular token via /api/v1/jobToken/exchange.

    Args:
        personal_token: PAT from qoder.com/account/integrations (pt-xxx format)
        timeout: Request timeout in seconds

    Returns:
        Dict with:
            - access_token: Regular token for API calls
            - refresh_token: For token refresh
            - expires_in: Token lifetime in seconds
            - refresh_token_expires_in: Refresh token lifetime

    Raises:
        Exception on exchange failure
    """
    if not personal_token:
        raise ValueError("exchange_personal_token: missing personal_token")

    url = f"{QODER_OPENAPI_BASE}/api/v1/jobToken/exchange"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            url,
            json={"personal_token": personal_token},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    if response.status_code != 200:
        message = f"PAT exchange failed: HTTP {response.status_code}"
        try:
            body = response.json()
            if body.get("message"):
                message = f"PAT exchange failed: {body['message']}"
        except Exception:
            pass
        raise Exception(message)

    data = response.json()

    # Token can be in multiple fields (qodercli checks all)
    access_token = (
        data.get("token")
        or data.get("device_token")
        or data.get("access_token")
    )
    if not access_token:
        raise Exception("PAT exchange failed: no token in response")

    # Parse expiry times (multiple formats supported)
    expires_in = (
        data.get("expires_in")
        or data.get("expireTimeS")
    )
    refresh_token_expires_in = (
        data.get("refresh_token_expires_in")
        or data.get("refreshTokenExpireTimeS")
    )

    return {
        "access_token": access_token,
        "refresh_token": data.get("refreshToken") or data.get("refresh_token"),
        "expires_in": expires_in,
        "refresh_token_expires_in": refresh_token_expires_in,
    }


# Client errors that mean this refresh token will not work again.
_DEAD_REFRESH_HTTP = frozenset({400, 401, 403})


def refresh_token_unusable(data: dict[str, Any]) -> bool:
    """True when this exact refresh token already got a terminal reject."""
    token = data.get("refreshToken")
    if not token:
        return True
    return data.get("invalidRefreshToken") == token


def mark_refresh_rejected(
    data: dict[str, Any],
    status_code: int | None,
) -> None:
    """Persist a dead refresh token so background refresh skips it."""
    token = data.get("refreshToken")
    if token:
        data["invalidRefreshToken"] = token
    data["testStatus"] = "unavailable"
    if status_code is not None:
        data["errorCode"] = str(status_code)
    data["lastError"] = "jobToken/refresh rejected"
    data["lastErrorAt"] = datetime.now(timezone.utc).isoformat()


def apply_refreshed_qoder_tokens(
    data: dict[str, Any],
    new_tokens: dict[str, Any],
) -> None:
    """Write a successful refresh and clear any dead-token mark."""
    data["accessToken"] = new_tokens["access_token"]
    data["refreshToken"] = new_tokens["refresh_token"]
    apply_qoder_token_expiry(data, new_tokens)
    data["testStatus"] = "connected"
    data.pop("invalidRefreshToken", None)
    data.pop("lastError", None)
    data.pop("lastErrorAt", None)
    data.pop("errorCode", None)


async def _sync_quota_after_refresh(
    db: Any,
    connection_id: str,
    data: dict[str, Any],
) -> None:
    """GET quota/usage after a real token recover. Fail-open."""
    try:
        from app.providers.qoder import quota as qoder_quota

        await qoder_quota.sync_quota_after_token_refresh(
            db,
            connection_id,
            data.get("accessToken") or "",
            data,
        )
    except Exception as e:
        logger.warning(
            "Qoder refresh usage sync failed for %s: %s",
            connection_id, e,
        )


async def refresh_job_token_result(
    refresh_token: str,
    timeout: float = 15.0,
) -> tuple[dict[str, Any] | None, int | None]:
    """POST jobToken/refresh. Returns (tokens, http_status)."""
    if not refresh_token:
        return None, None

    async with create_upstream_client(timeout=timeout) as client:
        response = await client.post(
            QODER_REFRESH_TOKEN_URL,
            json={"refresh_token": refresh_token},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    if response.status_code != 200:
        logger.warning(
            "Qoder jobToken/refresh HTTP %s: %s",
            response.status_code,
            (response.text or "")[:200],
        )
        return None, response.status_code

    data = response.json()

    access_token = (
        data.get("token")
        or data.get("device_token")
        or data.get("access_token")
    )
    if not access_token:
        return None, response.status_code

    expires_in = data.get("expires_in") or data.get("expireTimeS")
    refresh_token_expires_in = (
        data.get("refresh_token_expires_in")
        or data.get("refreshTokenExpireTimeS")
    )
    new_refresh_token = data.get("refreshToken") or data.get("refresh_token")

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token or refresh_token,
        "expires_in": expires_in,
        "refresh_token_expires_in": refresh_token_expires_in,
        "expires_at": data.get("expires_at") or data.get("expiresAt"),
        "refresh_token_expires_at": (
            data.get("refresh_token_expires_at")
            or data.get("refreshTokenExpiresAt")
        ),
    }, response.status_code


async def refresh_job_token(
    refresh_token: str,
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Refresh a Qoder job token using the refresh token.

    Uses POST /api/v1/jobToken/refresh on openapi.qoder.sh
    (same endpoint qodercli uses). Returns None if the refresh
    token itself is expired/invalid.

    Args:
        refresh_token: jrt-* (PAT exchange) or drt-* (OAuth / device)
        timeout: Request timeout in seconds

    Returns:
        Dict with access_token, refresh_token, expires_in — or None on failure
    """
    tokens, _status = await refresh_job_token_result(
        refresh_token, timeout=timeout,
    )
    return tokens


async def import_pat(
    personal_token: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Import a PAT token and return connection data.

    Full flow:
    1. Exchange PAT for regular token
    2. Fetch user info with regular token
    3. Return data for creating a connection

    Args:
        personal_token: PAT from qoder.com/account/integrations (pt-xxx format)
        timeout: Request timeout in seconds

    Returns:
        Dict with connection data:
            - access_token: Regular token for COSY signing
            - refresh_token: For token refresh
            - expires_in: Token lifetime
            - user_id: Qoder user ID
            - email: User email
            - display_name: User display name
            - machine_id: Generated machine ID

    Raises:
        Exception on import failure
    """
    # Step 1: Exchange PAT for regular token
    token_data = await exchange_personal_token(personal_token, timeout=timeout)
    access_token = token_data["access_token"]

    # Step 2: Fetch user info
    user_info = await fetch_user_info(access_token, timeout=timeout)

    # Step 3: Generate machine ID (for COSY signing)
    machine_id = str(uuid.uuid4())

    # Qoder returns 'id' not 'userId' or 'uid'
    user_id = user_info.get("id") or user_info.get("uid") or user_info.get("userId")

    return {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "user_id": user_id,
        "email": user_info.get("email"),
        "display_name": user_info.get("name") or user_info.get("displayName"),
        "machine_id": machine_id,
        "organization_id": user_info.get("organization_id"),
    }


def stored_personal_token(data: dict[str, Any]) -> str | None:
    """PAT from connection data; None when absent."""
    raw = data.get("personalToken") or data.get("personal_token")
    if not isinstance(raw, str):
        return None
    token = raw.strip()
    return token or None


async def recover_qoder_tokens(
    data: dict[str, Any],
) -> tuple[dict[str, Any] | None, int | None]:
    """Refresh the job token, or re-exchange a stored PAT.

    Status is the HTTP code from jobToken/refresh only (None
    when that call is skipped).
    """
    refresh_token = data.get("refreshToken")
    status: int | None = None
    if refresh_token and not refresh_token_unusable(data):
        tokens, status = await refresh_job_token_result(
            refresh_token,
        )
        if tokens:
            return tokens, status
    pat = stored_personal_token(data)
    if not pat:
        return None, status
    try:
        exchanged = await exchange_personal_token(pat)
    except Exception as exc:
        logger.warning("Qoder PAT re-exchange failed: %s", exc)
        return None, status
    if not exchanged.get("access_token"):
        return None, status
    return exchanged, status


async def try_refresh_connection(db, connection_id: str) -> bool:
    """Refresh job tokens; fall back to stored PAT exchange.

    Called by the proxy when a 401/403 is received from Qoder
    upstream. Updates accessToken and refreshToken in the DB.
    personalToken is kept so later export can recover the
    account after job tokens expire.
    """
    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.id == connection_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn or not conn.data:
        return False

    data = json.loads(conn.data)
    if (
        not data.get("refreshToken")
        and not stored_personal_token(data)
    ):
        logger.warning(
            "Qoder refresh: no refresh_token or PAT for %s",
            connection_id,
        )
        return False

    proxy = await proxy_for_connection(db, conn, "oauthRefresh")
    async with use_outbound_proxy(proxy):
        new_tokens, status = await recover_qoder_tokens(data)
    if not new_tokens:
        if status in _DEAD_REFRESH_HTTP:
            mark_refresh_rejected(data, status)
            conn.data = json.dumps(data)
            await db.flush()
            proxy_service.invalidate_connection_cache("qoder")
        logger.warning(
            "Qoder refresh: recover failed for connection %s",
            connection_id,
        )
        return False

    apply_refreshed_qoder_tokens(data, new_tokens)
    conn.data = json.dumps(data)

    await db.flush()
    proxy_service.invalidate_connection_cache("qoder")
    await _sync_quota_after_refresh(db, str(connection_id), data)
    logger.info(
        "Qoder refresh: token refreshed for connection %s",
        connection_id,
    )
    return True


async def refresh_all_qoder_connections() -> dict[str, bool]:
    """Refresh active Qoder job tokens that are near expiry.

    Called every 5 min via token_refresh_loop. Skips tokens whose
    expiresAt is still outside QODER_JOB_TOKEN_REFRESH_BUFFER_S.
    Idle accounts still stay alive; they are not POSTed every cycle.

    Returns:
        Dict mapping connection_id -> success bool
    """
    logger = logging.getLogger(__name__)
    results: dict[str, bool] = {}

    async_session = database.async_sessionmaker(
        database.engine, expire_on_commit=False,
    )
    async with async_session() as db:
        stmt = select(ProviderConnection).where(
            ProviderConnection.provider == "qoder",
            ProviderConnection.is_active == True,
        )
        rows = await db.execute(stmt)
        connections = rows.scalars().all()

        skipped_dead = 0
        for conn in connections:
            data = json.loads(conn.data) if conn.data else {}
            refresh_token = data.get("refreshToken")
            pat = stored_personal_token(data)
            if not refresh_token and not pat:
                continue

            conn_id = str(conn.id)
            if (
                refresh_token_unusable(data)
                and not pat
            ):
                skipped_dead += 1
                continue
            if not job_token_needs_refresh(data):
                continue

            proxy = await proxy_for_connection(db, conn, "oauthRefresh")
            async with use_outbound_proxy(proxy):
                new_tokens, status = await recover_qoder_tokens(
                    data,
                )
            if not new_tokens:
                if status in _DEAD_REFRESH_HTTP:
                    mark_refresh_rejected(data, status)
                    conn.data = json.dumps(data)
                    db.add(conn)
                logger.warning(
                    "Qoder background refresh FAILED: %s... "
                    "(jobToken/refresh rejected)",
                    conn_id[:8],
                )
                results[conn_id] = False
                continue

            apply_refreshed_qoder_tokens(data, new_tokens)
            conn.data = json.dumps(data)
            db.add(conn)
            await _sync_quota_after_refresh(db, conn_id, data)

            logger.info(f"Qoder background refresh OK: {conn_id[:8]}...")
            results[conn_id] = True

        if skipped_dead:
            logger.info(
                "Qoder background refresh SKIP: %d connection(s) "
                "with invalid refresh token",
                skipped_dead,
            )

        await db.commit()

    # Invalidate proxy cache after all refreshes
    try:
        proxy_service.invalidate_connection_cache("qoder")
    except Exception:
        pass

    return results
