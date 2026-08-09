"""OAuth provider authentication endpoints.

Handles authorization code flows (with/without PKCE), device code flows,
and special flows (cursor import, codex proxy).
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.providers import PROVIDER_GROK_CLI, PROVIDER_QODER
from app.providers.codex.proxy import CodexProxy
from app.providers.grok_cli.bulk import (
    is_expired,
    parse_farm_entry as parse_grok_farm_entry,
)
from app.providers.qoder.bulk import (
    parse_farm_entry as parse_qoder_farm_entry,
)
from app.providers.cursor.oauth import CursorImportRequest
from app.providers.gitlab.oauth import GitLabPATRequest
from app.providers.kiro.oauth import KiroImportRequest, KiroSocialExchangeRequest
from app.providers.qoder.auth import import_pat
from app.providers.qoder.oauth import QoderPATRequest
from app.services.oauth import (
    generate_auth_data,
    exchange_tokens,
    request_device_code,
    poll_for_token,
    get_oauth_handler,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

# ── Codex Proxy (lazy-init, receives save_connection callback) ────────────────

_codex_proxy: Optional[CodexProxy] = None


def _get_codex_proxy() -> CodexProxy:
    global _codex_proxy
    if _codex_proxy is None:
        _codex_proxy = CodexProxy(
            exchange_fn=exchange_tokens,
            save_connection_fn=_save_connection,
        )
    return _codex_proxy


# ── Request/Response Models ──────────────────────────────────────────────────


class AuthorizeResponse(BaseModel):
    authUrl: Optional[str] = None
    state: str
    codeVerifier: str
    codeChallenge: str
    redirectUri: str
    flowType: str


class ExchangeRequest(BaseModel):
    code: str
    redirectUri: str = "http://localhost:8080/callback"
    codeVerifier: str = ""
    state: str = ""
    meta: Optional[dict] = None


class DeviceCodeResponse(BaseModel):
    device_code: Optional[str] = None
    user_code: Optional[str] = None
    verification_uri: Optional[str] = None
    verification_uri_complete: Optional[str] = None
    expires_in: Optional[int] = None
    interval: int = 5
    codeVerifier: str = ""
    # Extra data needed for polling (e.g. kiro client credentials)
    extra: Optional[dict] = None


class PollRequest(BaseModel):
    deviceCode: str
    codeVerifier: str = ""
    extraData: Optional[dict] = None


class TokenImportRequest(BaseModel):
    accessToken: str
    machineId: str = ""


class ConnectionResponse(BaseModel):
    id: str
    provider: str
    email: Optional[str] = None
    displayName: Optional[str] = None


class OAuthExchangeResponse(BaseModel):
    success: bool
    connection: Optional[ConnectionResponse] = None
    error: Optional[str] = None


class OAuthPollResponse(BaseModel):
    success: bool
    connection: Optional[ConnectionResponse] = None
    error: Optional[str] = None
    errorDescription: Optional[str] = None
    pending: bool = False


# ── Helper ───────────────────────────────────────────────────────────────────


async def _save_connection(
    db: AsyncSession,
    provider: str,
    token_data: dict,
    auth_type: str = "oauth",
) -> ProviderConnection:
    """Create or update a ProviderConnection from OAuth token data."""
    now = datetime.now(timezone.utc)

    # Build the data JSON blob
    data = {}
    if token_data.get("accessToken"):
        data["accessToken"] = token_data["accessToken"]
    if token_data.get("refreshToken"):
        data["refreshToken"] = token_data["refreshToken"]
    if token_data.get("idToken"):
        data["idToken"] = token_data["idToken"]
    if token_data.get("expiresIn"):
        data["expiresAt"] = datetime.fromtimestamp(
            now.timestamp() + token_data["expiresIn"], tz=timezone.utc
        ).isoformat()
    if token_data.get("scope"):
        data["scope"] = token_data["scope"]
    if token_data.get("apiKey"):
        data["apiKey"] = token_data["apiKey"]
    if token_data.get("projectId"):
        data["projectId"] = token_data["projectId"]
    if token_data.get("displayName"):
        data["displayName"] = token_data["displayName"]
    if token_data.get("providerSpecificData"):
        data.update(token_data["providerSpecificData"])

    email = token_data.get("email")
    display_name = token_data.get("displayName")
    data["testStatus"] = "active"

    # Auto-derive alias from provider config so models get correct prefix
    try:
        from app.providers.provider import Provider
        p = Provider(provider)
        data["alias"] = p.alias()
    except (ValueError, ModuleNotFoundError):
        pass

    conn = ProviderConnection(
        provider=provider,
        auth_type=auth_type,
        name=display_name or email or f"{provider} {'PAT' if auth_type == 'apikey' else 'OAuth'}",
        email=email,
        data=json.dumps(data),
    )
    db.add(conn)
    await db.flush()
    return conn


def _apply_absolute_expiry(
    conn: ProviderConnection, expires_at: Optional[str],
) -> None:
    """Override the expiresIn-derived expiry with an absolute one."""
    if not expires_at:
        return
    blob = json.loads(conn.data or "{}")
    blob["expiresAt"] = expires_at
    conn.data = json.dumps(blob)


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/{provider}/authorize")
async def authorize(provider: str, redirect_uri: str = "http://localhost:8080/callback"):
    """Generate OAuth authorization URL and PKCE data."""
    try:
        auth_data = generate_auth_data(provider, redirect_uri)
        return auth_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"OAuth authorize error for {provider}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider}/exchange")
async def exchange(
    provider: str,
    body: ExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange authorization code for tokens and save to database."""
    try:
        if not body.code:
            raise HTTPException(status_code=400, detail="Missing code")

        handler = get_oauth_handler(provider)

        # import_token flow: handler manages its own token import
        if handler.flow_type == "import_token":
            raw_data = await handler.import_token(
                body.code, **(body.meta or {})
            )
            token_data = handler.map_tokens(raw_data)
            conn = await _save_connection(db, provider, token_data)
            return OAuthExchangeResponse(
                success=True,
                connection=ConnectionResponse(
                    id=str(conn.id),
                    provider=conn.provider,
                    email=conn.email,
                    displayName=conn.name,
                ),
            )

        # authorization_code flows
        if not body.redirectUri:
            raise HTTPException(status_code=400, detail="Missing redirectUri")
        if handler.needs_pkce() and not body.codeVerifier:
            raise HTTPException(status_code=400, detail="Missing codeVerifier")

        token_data = await exchange_tokens(
            provider, body.code, body.redirectUri, body.codeVerifier, body.state, body.meta
        )

        conn = await _save_connection(db, provider, token_data)
        return OAuthExchangeResponse(
            success=True,
            connection=ConnectionResponse(
                id=str(conn.id),
                provider=conn.provider,
                email=conn.email,
                displayName=conn.name,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"OAuth exchange error for {provider}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider}/device-code")
async def device_code(
    provider: str,
    start_url: Optional[str] = None,
    region: Optional[str] = None,
    auth_method: Optional[str] = None,
):
    """Request a device code for device_code flow providers."""
    try:
        handler = get_oauth_handler(provider)
        if handler.flow_type not in ("device_code", "polling"):
            raise HTTPException(status_code=400, detail="Provider does not support device code flow")

        options = {}
        if start_url:
            options["startUrl"] = start_url
        if region:
            options["region"] = region
        if auth_method:
            options["authMethod"] = auth_method

        device_data = await request_device_code(provider, options=options or None)

        # Extract internal handler data (prefixed with _) into extra
        extra = {}
        for key in list(device_data):
            if key.startswith("_"):
                extra[key] = device_data.pop(key)

        return DeviceCodeResponse(
            device_code=device_data.get("device_code"),
            user_code=device_data.get("user_code"),
            verification_uri=device_data.get("verification_uri"),
            verification_uri_complete=device_data.get("verification_uri_complete"),
            expires_in=device_data.get("expires_in"),
            interval=device_data.get("interval", 5),
            codeVerifier=device_data.get("codeVerifier") or "",
            extra=extra if extra else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"OAuth device-code error for {provider}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider}/poll")
async def poll(
    provider: str,
    body: PollRequest,
    db: AsyncSession = Depends(get_db),
):
    """Poll for device code token. Creates connection on success."""
    try:
        # Handler decides whether to use code_verifier (PKCE) or ignore it
        result = await poll_for_token(
            provider,
            body.deviceCode,
            body.codeVerifier,
            body.extraData,
        )

        if result.get("success"):
            conn = await _save_connection(db, provider, result["tokens"])
            await db.commit()
            return OAuthPollResponse(
                success=True,
                connection=ConnectionResponse(
                    id=str(conn.id),
                    provider=conn.provider,
                    email=conn.email,
                    displayName=conn.name,
                ),
            )

        is_pending = result.get("pending") or result.get("error") in ("authorization_pending", "slow_down")
        return OAuthPollResponse(
            success=False,
            error=result.get("error"),
            errorDescription=result.get("errorDescription"),
            pending=is_pending,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"OAuth poll error for {provider}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider}/import-token")
async def import_token(
    provider: str,
    body: TokenImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import a token directly (handler dispatches via flow_type)."""
    try:
        handler = get_oauth_handler(provider)
        raw_data = await handler.import_token(body.accessToken, machineId=body.machineId)
        token_data = handler.map_tokens(raw_data)
        conn = await _save_connection(db, provider, token_data)
        return OAuthExchangeResponse(
            success=True,
            connection=ConnectionResponse(
                id=str(conn.id),
                provider=conn.provider,
                email=conn.email,
                displayName=conn.name,
            ),
        )
    except NotImplementedError:
        raise HTTPException(status_code=400, detail=f"Provider {provider} does not support import token")
    except Exception as e:
        logger.exception(f"OAuth import-token error for {provider}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Cursor Endpoints ─────────────────────────────────────────────────────────


@router.get("/cursor/auto-import")
async def cursor_auto_import():
    """Auto-detect Cursor tokens from local SQLite database."""
    try:
        return await get_oauth_handler("cursor").auto_import()
    except Exception as e:
        logger.exception("Cursor auto-import error")
        return {"found": False, "error": str(e)}


@router.post("/cursor/import")
async def cursor_import(body: CursorImportRequest, db: AsyncSession = Depends(get_db)):
    """Import and validate token from Cursor IDE."""
    try:
        if not body.accessToken or not isinstance(body.accessToken, str):
            raise HTTPException(status_code=400, detail="Access token is required")
        if not body.machineId or not isinstance(body.machineId, str):
            raise HTTPException(status_code=400, detail="Machine ID is required")
        token_data = await get_oauth_handler("cursor").validate_import_token(body.accessToken.strip(), body.machineId.strip())
        conn = await _save_connection(db, "cursor", token_data)
        return OAuthExchangeResponse(success=True, connection=ConnectionResponse(id=str(conn.id), provider=conn.provider, email=conn.email, displayName=conn.name))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cursor import token error")
        raise HTTPException(status_code=500, detail=str(e))


# ── Kiro Endpoints ───────────────────────────────────────────────────────────


@router.get("/kiro/auto-import")
async def kiro_auto_import():
    """Auto-detect Kiro refresh token from AWS SSO cache."""
    try:
        return await get_oauth_handler("kiro").auto_import()
    except Exception as e:
        logger.exception("Kiro auto-import error")
        return {"found": False, "error": str(e)}


@router.post("/kiro/import")
async def kiro_import(body: KiroImportRequest, db: AsyncSession = Depends(get_db)):
    """Import and validate refresh token from Kiro IDE."""
    try:
        if not body.refreshToken or not isinstance(body.refreshToken, str):
            raise HTTPException(status_code=400, detail="Refresh token is required")
        handler = get_oauth_handler("kiro")
        token_data = await handler.validate_import_token(body.refreshToken.strip())
        save_data = handler.build_import_data(token_data, body.refreshToken.strip())
        conn = await _save_connection(db, "kiro", save_data)
        return OAuthExchangeResponse(success=True, connection=ConnectionResponse(id=str(conn.id), provider=conn.provider, email=conn.email, displayName=conn.name))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Kiro import token error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kiro/social-authorize")
async def kiro_social_authorize(provider: str = ""):
    """Generate Google/GitHub social login URL for Kiro via AWS Cognito."""
    try:
        if provider not in ("google", "github"):
            raise HTTPException(status_code=400, detail="Invalid provider. Use 'google' or 'github'")
        from app.utils.pkce import generate_pkce
        pkce = generate_pkce()
        handler = get_oauth_handler("kiro")
        auth_url = handler.build_social_login_url(provider, pkce["codeChallenge"], pkce["state"])
        return {"authUrl": auth_url, "state": pkce["state"], "codeVerifier": pkce["codeVerifier"], "codeChallenge": pkce["codeChallenge"], "provider": provider}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Kiro social authorize error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kiro/social-exchange")
async def kiro_social_exchange(body: KiroSocialExchangeRequest, db: AsyncSession = Depends(get_db)):
    """Exchange authorization code for tokens (Kiro Google/GitHub social login)."""
    try:
        if not body.code or not body.codeVerifier:
            raise HTTPException(status_code=400, detail="Missing required fields")
        if body.provider not in ("google", "github"):
            raise HTTPException(status_code=400, detail="Invalid provider")
        handler = get_oauth_handler("kiro")
        token_data = await handler.exchange_social_code(body.code, body.codeVerifier)
        save_data = handler.build_social_save_data(token_data, body.provider)
        conn = await _save_connection(db, "kiro", save_data)
        return OAuthExchangeResponse(success=True, connection=ConnectionResponse(id=str(conn.id), provider=conn.provider, email=conn.email, displayName=conn.name))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Kiro social exchange error")
        raise HTTPException(status_code=500, detail=str(e))


# ── Codex Proxy Endpoints ────────────────────────────────────────────────────


@router.get("/codex/start-proxy")
async def codex_start_proxy(
    app_port: int = 5173,
    state: str = "",
    code_verifier: str = "",
    redirect_uri: str = "",
):
    """Start the Codex OAuth proxy server on port 1455 and register session."""
    try:
        return _get_codex_proxy().start(app_port, state, code_verifier, redirect_uri)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Codex start-proxy error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/codex/poll-status")
async def codex_poll_status(state: str = ""):
    """Poll for Codex OAuth session status (used by frontend to detect completion)."""
    try:
        return _get_codex_proxy().poll_status(state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Codex poll-status error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/codex/stop-proxy")
async def codex_stop_proxy():
    """Stop the Codex OAuth proxy server."""
    _get_codex_proxy().stop()
    return {"success": True}


# ── GitLab PAT Endpoint ─────────────────────────────────────────────────────


@router.post("/gitlab/pat")
async def gitlab_pat(
    body: GitLabPATRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with GitLab using a Personal Access Token."""
    try:
        handler = get_oauth_handler("gitlab")
        token_data = await handler.validate_pat(body.accessToken, body.baseUrl or "")
        conn = await _save_connection(db, "gitlab", token_data)
        return OAuthExchangeResponse(
            success=True,
            connection=ConnectionResponse(
                id=str(conn.id),
                provider=conn.provider,
                email=conn.email,
                displayName=conn.name,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("GitLab PAT authentication error")
        raise HTTPException(status_code=500, detail=str(e))


# ── Qoder PAT Endpoint ──────────────────────────────────────────────────────


@router.post("/qoder/pat")
async def qoder_pat_import(
    body: QoderPATRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import a Qoder Personal Access Token (PAT).

    The PAT (pt-xxx) is exchanged for a regular token via
    /api/v1/jobToken/exchange, then used for COSY-signed requests.
    """
    try:
        # from app.providers.qoder.auth import import_pat

        # Import PAT: exchange for regular token + fetch user info
        result = await import_pat(body.personalToken)

        token_data = {
            "accessToken": result["access_token"],
            "refreshToken": result.get("refresh_token"),
            "expiresIn": result.get("expires_in"),
            "email": result.get("email"),
            "displayName": result.get("display_name"),
            "providerSpecificData": {
                "userId": result.get("user_id"),
                "machineId": result.get("machine_id"),
                "organizationId": result.get("organization_id"),
                "loginMethod": "pat",
            },
        }

        conn = await _save_connection(db, "qoder", token_data, auth_type="apikey")
        return OAuthExchangeResponse(
            success=True,
            connection=ConnectionResponse(
                id=str(conn.id),
                provider=conn.provider,
                email=conn.email,
                displayName=conn.name,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Qoder PAT import error")
        raise HTTPException(status_code=500, detail=str(e))


# ── Bulk Import (grok-farm-modular style JSON exports) ──────────────

# provider -> (farm entry parser, connection auth_type)
_BULK_PARSERS: dict[str, tuple[Callable[[Any], dict], str]] = {
    PROVIDER_GROK_CLI: (parse_grok_farm_entry, "oauth"),
    PROVIDER_QODER: (parse_qoder_farm_entry, "apikey"),
}


@router.post("/{provider}/bulk-import")
async def provider_bulk_import(
    provider: str,
    request: Request,
    replace: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Bulk import grok-farm-modular account exports.

    Body accepts an array, a single object, or ``{"accounts": [...]}``.
    Each entry needs ``email`` + ``tokens.access_token`` (farm format).
    Entries with an expired ``tokens.expires_at`` are skipped. Existing
    emails are upserted when ``replace=true``, otherwise skipped.
    Tokens are never echoed back in the response.
    """
    entry = _BULK_PARSERS.get(provider)
    if entry is None:
        raise HTTPException(
            status_code=400,
            detail=f"Bulk import not supported for '{provider}'",
        )
    parse_farm_entry, auth_type = entry

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON body: {e}",
        )

    if isinstance(body, list):
        accounts = body
    elif isinstance(body, dict) and isinstance(body.get("accounts"), list):
        accounts = body["accounts"]
    elif isinstance(body, dict):
        accounts = [body]
    else:
        accounts = None

    if not accounts:
        raise HTTPException(status_code=400, detail="No accounts provided")

    counts = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    results: list[dict] = []

    # Serial loop — connection creation touches shared state (priority);
    # parallel calls would race (mirrors the Node.js reference).
    for i, raw in enumerate(accounts):
        try:
            parsed = parse_farm_entry(raw)
        except ValueError as e:
            results.append({
                "index": i, "status": "failed", "error": str(e),
            })
            counts["failed"] += 1
            continue

        email = parsed["email"]
        if is_expired(parsed["expires_at"]):
            results.append({
                "index": i, "email": email, "status": "skipped_expired",
            })
            counts["skipped"] += 1
            continue

        existing = (await db.execute(
            select(ProviderConnection).where(
                ProviderConnection.provider == provider,
                func.lower(ProviderConnection.email) == email,
            )
        )).scalar_one_or_none()

        if existing and not replace:
            results.append({
                "index": i, "email": email, "status": "skipped_duplicate",
            })
            counts["skipped"] += 1
            continue

        if existing:
            _update_bulk_connection(existing, parsed)
            status = "updated"
        else:
            conn = await _save_connection(
                db, provider, parsed["token_data"], auth_type=auth_type,
            )
            _apply_absolute_expiry(conn, parsed["expires_at"])
            status = "created"

        results.append({"index": i, "email": email, "status": status})
        counts[status] += 1

    await db.commit()
    return {**counts, "results": results}


def _update_bulk_connection(conn: ProviderConnection, parsed: dict) -> None:
    """Replace credentials on an existing connection (upsert path)."""
    token_data = parsed["token_data"]
    blob = json.loads(conn.data or "{}")
    blob["accessToken"] = token_data["accessToken"]
    if token_data.get("refreshToken"):
        blob["refreshToken"] = token_data["refreshToken"]
    if token_data.get("scope"):
        blob["scope"] = token_data["scope"]
    if parsed["expires_at"]:
        blob["expiresAt"] = parsed["expires_at"]
    # providerSpecificData lands flat in the blob (see _save_connection)
    psd = token_data.get("providerSpecificData") or {}
    for key, value in psd.items():
        if value is not None:
            blob[key] = value
    blob["testStatus"] = "active"
    conn.data = json.dumps(blob)
    # Bulk-imported connections are always named by email
    conn.name = parsed["email"]
    conn.email = parsed["email"]
