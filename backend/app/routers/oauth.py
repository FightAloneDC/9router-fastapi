"""OAuth provider authentication endpoints.

Handles authorization code flows (with/without PKCE), device code flows,
and special flows (cursor import, cline callback, codex proxy).
"""

import asyncio
import json
import logging
import subprocess
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import urlparse, parse_qs

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.providers import (
    PROVIDER_CODEX,
    PROVIDER_CURSOR,
    PROVIDER_GITLAB,
    PROVIDER_KIRO,
    PROVIDER_QODER,
)
from app.services.oauth import (
    generate_auth_data,
    exchange_tokens,
    request_device_code,
    poll_for_token,
    get_oauth_handler,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

# ── Codex Proxy State ───────────────────────────────────────────────────────
# Codex OAuth uses a local proxy server on port 1455 that auto-exchanges
# tokens server-side when the callback arrives.

CODEX_PORT = 1455
CODEX_PROXY_TIMEOUT_S = 300  # 5 minutes

_codex_sessions: dict = {}  # keyed by state string
_codex_proxy_server: Optional[HTTPServer] = None
_codex_proxy_thread: Optional[threading.Thread] = None
_codex_proxy_timer: Optional[threading.Timer] = None


def _render_codex_result_page(success: bool, message: str) -> str:
    color = "#22c55e" if success else "#ef4444"
    icon = "&#10003;" if success else "&#10007;"
    title = "Authentication Successful" if success else "Authentication Failed"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5}}.c{{text-align:center;padding:2rem;background:#fff;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1)}}.i{{color:{color};font-size:3rem}}h1{{margin:1rem 0}}p{{color:#666}}</style>
</head><body><div class="c"><div class="i">{icon}</div><h1>{title}</h1><p>{message}</p><p>Closing in <span id="cd">3</span>s...</p>
<script>let n=3;const c=document.getElementById("cd");const t=setInterval(()=>{{n--;c.textContent=n;if(n<=0){{clearInterval(t);window.close();}}}},1000);</script>
</div></body></html>"""


class _CodexCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Codex OAuth callback proxy on port 1455."""

    def log_message(self, format, *args):
        logger.info(f"Codex proxy: {format % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path not in ("/callback", "/auth/callback"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error_param = params.get("error", [None])[0]
        session = _codex_sessions.get(state) if state else None

        if session:
            try:
                if error_param:
                    raise Exception(params.get("error_description", [error_param])[0])
                if not code:
                    raise Exception("No authorization code received")

                # Exchange tokens synchronously (we're in a thread)
                loop = asyncio.new_event_loop()
                try:
                    token_data = loop.run_until_complete(
                        exchange_tokens(
                            PROVIDER_CODEX, code, session["redirectUri"],
                            session["codeVerifier"], state or ""
                        )
                    )
                finally:
                    loop.close()

                # Save connection synchronously
                loop = asyncio.new_event_loop()
                try:
                    conn = loop.run_until_complete(
                        _save_connection_sync(PROVIDER_CODEX, token_data)
                    )
                finally:
                    loop.close()

                session["status"] = "done"
                session["connectionId"] = str(conn.id)
                session["email"] = conn.email

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    _render_codex_result_page(True, "You can close this window.").encode()
                )
            except Exception as err:
                session["status"] = "error"
                session["error"] = str(err)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(_render_codex_result_page(False, str(err)).encode())
            finally:
                _stop_codex_proxy()
            return

        # No matching session — redirect to app port fallback
        app_port = "5173"
        for s in _codex_sessions.values():
            app_port = s.get("appPort", "5173")
            break
        redirect_url = f"http://localhost:{app_port}/callback?{parsed.query}"
        self.send_response(302)
        self.send_header("Location", redirect_url)
        self.end_headers()


async def _save_connection_sync(provider: str, token_data: dict):
    """Save connection from the proxy thread using a new async session."""
    from app.database import async_session
    async with async_session() as db:
        conn = await _save_connection(db, provider, token_data)
        await db.commit()
        return conn


def _start_codex_proxy_thread():
    """Start the codex proxy HTTP server in a background thread."""
    global _codex_proxy_server, _codex_proxy_thread

    if _codex_proxy_server is not None:
        return True

    try:
        _codex_proxy_server = HTTPServer(("0.0.0.0", CODEX_PORT), _CodexCallbackHandler)
        _codex_proxy_thread = threading.Thread(
            target=_codex_proxy_server.serve_forever, daemon=True
        )
        _codex_proxy_thread.start()
        logger.info(f"Codex proxy started on port {CODEX_PORT}")
        return True
    except OSError as e:
        logger.error(f"Failed to start codex proxy on port {CODEX_PORT}: {e}")
        return False


def _stop_codex_proxy():
    """Stop the codex proxy server and cleanup."""
    global _codex_proxy_server, _codex_proxy_thread, _codex_proxy_timer

    if _codex_proxy_timer:
        _codex_proxy_timer.cancel()
        _codex_proxy_timer = None

    if _codex_proxy_server:
        _codex_proxy_server.shutdown()
        _codex_proxy_server = None
        _codex_proxy_thread = None
        logger.info("Codex proxy stopped")


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


class GitLabPATRequest(BaseModel):
    accessToken: str
    baseUrl: Optional[str] = "https://gitlab.com"


class KiroImportRequest(BaseModel):
    refreshToken: str


class KiroSocialExchangeRequest(BaseModel):
    code: str
    codeVerifier: str
    provider: str  # "google" or "github"


class CursorImportRequest(BaseModel):
    accessToken: str
    machineId: str


class QoderPATRequest(BaseModel):
    personalToken: str


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
    """Import a token directly (used for cursor)."""
    try:
        if provider != PROVIDER_CURSOR:
            raise HTTPException(status_code=400, detail="Import token only supported for cursor")

        token_data = map_tokens(PROVIDER_CURSOR,
            {"accessToken": body.accessToken, "machineId": body.machineId},
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
    except Exception as e:
        logger.exception(f"OAuth import-token error for {provider}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Cursor Endpoints ─────────────────────────────────────────────────────────


@router.get("/cursor/auto-import")
async def cursor_auto_import():
    """Auto-detect Cursor tokens from local SQLite database."""
    try:
        import platform as _platform
        if _platform.system().lower() == "linux":
            cursor_installed = False
            try:
                result = subprocess.run(["which", "cursor"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    cursor_installed = True
            except Exception:
                pass
            if not cursor_installed:
                desktop_file = os.path.expanduser("~/.local/share/applications/cursor.desktop")
                if os.path.exists(desktop_file):
                    cursor_installed = True
            if not cursor_installed:
                return {"found": False, "error": "Cursor config files found but Cursor IDE does not appear to be installed. Skipping auto-import."}
        result = await get_oauth_handler(PROVIDER_CURSOR).auto_import()
        return result
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
        token_data = await get_oauth_handler(PROVIDER_CURSOR).validate_import_token(body.accessToken.strip(), body.machineId.strip())
        conn = await _save_connection(db, PROVIDER_CURSOR, token_data)
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
        return await get_oauth_handler(PROVIDER_KIRO).auto_import()
    except Exception as e:
        logger.exception("Kiro auto-import error")
        return {"found": False, "error": str(e)}


@router.post("/kiro/import")
async def kiro_import(body: KiroImportRequest, db: AsyncSession = Depends(get_db)):
    """Import and validate refresh token from Kiro IDE."""
    try:
        if not body.refreshToken or not isinstance(body.refreshToken, str):
            raise HTTPException(status_code=400, detail="Refresh token is required")
        handler = get_oauth_handler(PROVIDER_KIRO)
        token_data = await handler.validate_import_token(body.refreshToken.strip())
        save_data = handler.build_import_data(token_data, body.refreshToken.strip())
        conn = await _save_connection(db, PROVIDER_KIRO, save_data)
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
        handler = get_oauth_handler(PROVIDER_KIRO)
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
        handler = get_oauth_handler(PROVIDER_KIRO)
        token_data = await handler.exchange_social_code(body.code, body.codeVerifier)
        save_data = handler.build_social_save_data(token_data, body.provider)
        conn = await _save_connection(db, PROVIDER_KIRO, save_data)
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
    global _codex_proxy_timer

    if not state or not code_verifier or not redirect_uri:
        raise HTTPException(status_code=400, detail="Missing state, code_verifier, or redirect_uri")

    # Start proxy server if not running
    proxy_started = _start_codex_proxy_thread()
    if not proxy_started:
        return {"success": False, "reason": "port_busy"}

    # Register session for server-side auto-exchange
    _codex_sessions[state] = {
        "codeVerifier": code_verifier,
        "redirectUri": redirect_uri,
        "appPort": str(app_port),
        "status": "pending",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    # Auto-stop proxy after timeout
    if _codex_proxy_timer:
        _codex_proxy_timer.cancel()
    _codex_proxy_timer = threading.Timer(CODEX_PROXY_TIMEOUT_S, _stop_codex_proxy)
    _codex_proxy_timer.daemon = True
    _codex_proxy_timer.start()

    return {"success": True, "serverSide": True}


@router.get("/codex/poll-status")
async def codex_poll_status(state: str = ""):
    """Poll for Codex OAuth session status (used by frontend to detect completion)."""
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")

    session = _codex_sessions.get(state)
    if not session:
        return {"status": "unknown"}

    if session["status"] in ("done", "error"):
        payload = {**session}
        del _codex_sessions[state]
        return payload

    return {"status": session["status"]}


@router.get("/codex/stop-proxy")
async def codex_stop_proxy():
    """Stop the Codex OAuth proxy server."""
    _stop_codex_proxy()
    return {"success": True}


# ── GitLab PAT Endpoint ─────────────────────────────────────────────────────


@router.post("/gitlab/pat")
async def gitlab_pat(
    body: GitLabPATRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with GitLab using a Personal Access Token."""
    try:
        handler = get_oauth_handler(PROVIDER_GITLAB)
        token_data = await handler.validate_pat(body.accessToken, body.baseUrl or "")
        conn = await _save_connection(db, PROVIDER_GITLAB, token_data)
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
        from app.providers.qoder.auth import import_pat

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

        conn = await _save_connection(db, PROVIDER_QODER, token_data, auth_type="apikey")
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
