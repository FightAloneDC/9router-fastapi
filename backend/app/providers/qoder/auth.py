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
  PAT-exchanged job tokens (jt-xxx) expire in ~24 hours.
  qodercli uses /api/v1/jobToken/refresh (on openapi.qoder.sh) to get a new
  access token using the refresh_token.  The old endpoint on center.qoder.sh
  returns 403 — this one works.
"""

import base64
import hashlib
import secrets
import uuid
from typing import Any

import httpx

from app.services.outbound_proxy import (
    create_upstream_client,
    proxy_for_connection,
    use_outbound_proxy,
)

from .constants import (
    QODER_DEVICE_TOKEN_URL,
    QODER_LOGIN_URL,
    QODER_OPENAPI_BASE,
    QODER_REFRESH_TOKEN_URL,
    QODER_USERINFO_URL,
)


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
    import logging
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


async def refresh_job_token(
    refresh_token: str,
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Refresh a Qoder job token using the refresh token.

    Uses POST /api/v1/jobToken/refresh on openapi.qoder.sh
    (same endpoint qodercli uses). Returns None if the refresh
    token itself is expired/invalid.

    Args:
        refresh_token: The refresh_token (jrt-xxx) from the original exchange
        timeout: Request timeout in seconds

    Returns:
        Dict with access_token, refresh_token, expires_in — or None on failure
    """
    if not refresh_token:
        return None

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
        return None

    data = response.json()

    access_token = (
        data.get("token")
        or data.get("device_token")
        or data.get("access_token")
    )
    if not access_token:
        return None

    expires_in = data.get("expires_in") or data.get("expireTimeS")
    new_refresh_token = data.get("refreshToken") or data.get("refresh_token")

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token or refresh_token,
        "expires_in": expires_in,
    }


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


async def try_refresh_connection(db, connection_id: str) -> bool:
    """Try to refresh a Qoder connection's token using its refresh_token.

    Called by the proxy when a 401/403 is received from Qoder upstream.
    Updates the connection's accessToken and refreshToken in the DB.

    Args:
        db: AsyncSession
        connection_id: ProviderConnection UUID string

    Returns:
        True if refresh succeeded and DB was updated, False otherwise.
    """
    import json
    import logging
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.provider import ProviderConnection

    logger = logging.getLogger(__name__)

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn or not conn.data:
        return False

    data = json.loads(conn.data)
    refresh_token = data.get("refreshToken")
    if not refresh_token:
        logger.warning(f"Qoder refresh: no refresh_token for connection {connection_id}")
        return False

    proxy = await proxy_for_connection(db, conn, "oauthRefresh")
    async with use_outbound_proxy(proxy):
        new_tokens = await refresh_job_token(refresh_token)
    if not new_tokens:
        logger.warning(f"Qoder refresh: refresh_token expired for connection {connection_id}")
        return False

    # Update tokens in DB
    data["accessToken"] = new_tokens["access_token"]
    data["refreshToken"] = new_tokens["refresh_token"]
    data["testStatus"] = "connected"
    data.pop("lastError", None)
    data.pop("lastErrorAt", None)
    conn.data = json.dumps(data)

    await db.flush()

    # Invalidate proxy cache
    from app.services.proxy import invalidate_connection_cache
    invalidate_connection_cache("qoder")

    logger.info(f"Qoder refresh: token refreshed for connection {connection_id}")
    return True


async def refresh_all_qoder_connections() -> dict[str, bool]:
    """Background task: refresh all Qoder connections that have a refresh_token.

    Called periodically (every 5 min via token_refresh_loop) to keep tokens
    alive even when connections are idle.

    Returns:
        Dict mapping connection_id -> success bool
    """
    import json
    import logging
    from sqlalchemy import select
    from app.models.provider import ProviderConnection
    from app.database import async_sessionmaker, engine

    logger = logging.getLogger(__name__)
    results: dict[str, bool] = {}

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        stmt = select(ProviderConnection).where(
            ProviderConnection.provider == "qoder",
            ProviderConnection.is_active == True,
        )
        rows = await db.execute(stmt)
        connections = rows.scalars().all()

        for conn in connections:
            data = json.loads(conn.data) if conn.data else {}
            refresh_token = data.get("refreshToken")
            if not refresh_token:
                continue

            conn_id = str(conn.id)
            proxy = await proxy_for_connection(db, conn, "oauthRefresh")
            async with use_outbound_proxy(proxy):
                new_tokens = await refresh_job_token(refresh_token)
            if not new_tokens:
                logger.warning(f"Qoder background refresh FAILED: {conn_id[:8]}... (refresh_token expired)")
                results[conn_id] = False
                continue

            data["accessToken"] = new_tokens["access_token"]
            data["refreshToken"] = new_tokens["refresh_token"]
            data["testStatus"] = "connected"
            data.pop("lastError", None)
            data.pop("lastErrorAt", None)
            conn.data = json.dumps(data)
            db.add(conn)

            logger.info(f"Qoder background refresh OK: {conn_id[:8]}...")
            results[conn_id] = True

        await db.commit()

    # Invalidate proxy cache after all refreshes
    try:
        from app.services.proxy import invalidate_connection_cache
        invalidate_connection_cache("qoder")
    except Exception:
        pass

    return results
