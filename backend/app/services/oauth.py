"""OAuth service module — consolidated port from the original 9router Next.js project.

Contains:
  1. PKCE utilities (code verifier, challenge, state)
  2. OAuth config constants for every provider
  3. OAuthService class with device code flow, token exchange, refresh
  4. Provider-specific handler classes (Codex, GitHub, Kiro, Cursor, GitLab)
  5. Convenience module-level functions used by routers

Ported faithfully from:
  - src/lib/oauth/constants/oauth.js
  - src/lib/oauth/services/oauth.js
  - src/lib/oauth/services/{codex,github,kiro,cursor}.js
  - src/lib/oauth/utils/pkce.js
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import platform
import secrets
import sqlite3
import struct
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import settings
logger = logging.getLogger(__name__)

# ─── OAuth Timeout ───────────────────────────────────────────────────────────
OAUTH_TIMEOUT = 300000  # 5 minutes in ms (matches original)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PKCE Utilities
# ═══════════════════════════════════════════════════════════════════════════════


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier (43-128 characters).

    Uses secrets.token_bytes(32) → base64url encoding (no padding).
    Equivalent to the Node.js crypto.randomBytes(32).toString('base64url').
    """
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def generate_code_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier using S256 method.

    SHA-256 digest of the verifier, base64url-encoded without padding.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_state() -> str:
    """Generate random state token for CSRF protection."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def generate_pkce() -> dict:
    """Generate a complete PKCE pair with state.

    Returns dict with keys: codeVerifier, codeChallenge, state
    """
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = generate_state()
    return {
        "codeVerifier": code_verifier,
        "codeChallenge": code_challenge,
        "state": state,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. OAuth Configuration Constants
#    Ported from src/lib/oauth/constants/oauth.js
# ═══════════════════════════════════════════════════════════════════════════════


def _get_oauth_platform_enum() -> int:
    """Get the platform enum value based on the current OS.

    Matches Antigravity binary's ClientMetadata.Platform enum.
    """
    os_name = platform.system().lower()
    architecture = platform.machine().lower()
    if os_name == "darwin":
        return 2 if architecture == "arm64" else 1
    if os_name == "linux":
        return 4 if architecture == "arm64" else 3
    if os_name == "windows":
        return 5
    return 0


def get_oauth_client_metadata() -> dict:
    """Get client metadata using numeric enum values for API calls."""
    return {"ideType": 9, "platform": _get_oauth_platform_enum(), "pluginType": 2}


# ── Claude (Authorization Code Flow + PKCE) ──────────────────────────────────
CLAUDE_CONFIG: dict[str, Any] = {
    "clientId": settings.CLAUDE_CLIENT_ID,
    "authorizeUrl": "https://claude.ai/oauth/authorize",
    "tokenUrl": "https://api.anthropic.com/v1/oauth/token",
    "scopes": ["org:create_api_key", "user:profile", "user:inference"],
    "codeChallengeMethod": "S256",
}

# ── Codex / OpenAI (Authorization Code Flow + PKCE) ──────────────────────────
CODEX_CONFIG: dict[str, Any] = {
    "clientId": settings.CODEX_CLIENT_ID,
    "authorizeUrl": "https://auth.openai.com/oauth/authorize",
    "tokenUrl": "https://auth.openai.com/oauth/token",
    "scope": "openid profile email offline_access",
    "codeChallengeMethod": "S256",
    "extraParams": {
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "codex_cli_rs",
    },
}

OPENAI_CONFIG: dict[str, Any] = {
    "clientId": settings.CODEX_CLIENT_ID,
    "authorizeUrl": "https://auth.openai.com/oauth/authorize",
    "tokenUrl": "https://auth.openai.com/oauth/token",
    "scope": "openid profile email offline_access",
    "codeChallengeMethod": "S256",
    "extraParams": {
        "id_token_add_organizations": "true",
        "originator": "openai_native",
    },
}

# ── Gemini CLI (Google OAuth2) ───────────────────────────────────────────────
GEMINI_CONFIG: dict[str, Any] = {
    "clientId": settings.GEMINI_CLIENT_ID,
    "clientSecret": settings.GEMINI_CLIENT_SECRET,
    "authorizeUrl": "https://accounts.google.com/o/oauth2/v2/auth",
    "tokenUrl": "https://oauth2.googleapis.com/token",
    "userInfoUrl": "https://www.googleapis.com/oauth2/v1/userinfo",
    "scopes": [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
}

# ── Qwen (Device Code Flow + PKCE) ──────────────────────────────────────────
QWEN_CONFIG: dict[str, Any] = {
    "clientId": settings.QWEN_CLIENT_ID,
    "deviceCodeUrl": "https://chat.qwen.ai/api/v1/oauth2/device/code",
    "tokenUrl": "https://chat.qwen.ai/api/v1/oauth2/token",
    "scope": "openid profile email model.completion",
    "codeChallengeMethod": "S256",
}

# ── Qoder (Device Token Flow) ────────────────────────────────────────────────
QODER_CONFIG: dict[str, Any] = {
    "apiBaseUrl": "https://api2.qoder.sh",
    "deviceTokenUrl": "https://api2.qoder.sh/api/v1/deviceToken/poll",
    "deviceRefreshUrl": "https://api2.qoder.sh/api/v1/deviceToken/refresh",
    "refreshUrl": "https://api2.qoder.sh/api/v3/user/refresh_token",
    "userInfoUrl": "https://api2.qoder.sh/api/v1/userinfo",
    "statusUrl": "https://api2.qoder.sh/api/v3/user/status",
    "loginUrl": "https://qoder.com/login",
}

# ── iFlow (Authorization Code + Basic Auth) ──────────────────────────────────
IFLOW_CONFIG: dict[str, Any] = {
    "clientId": settings.IFLOW_CLIENT_ID,
    "clientSecret": settings.IFLOW_CLIENT_SECRET,
    "authorizeUrl": "https://iflow.cn/oauth",
    "tokenUrl": "https://iflow.cn/oauth/token",
    "userInfoUrl": "https://iflow.cn/api/oauth/getUserInfo",
    "extraParams": {
        "loginMethod": "phone",
        "type": "phone",
    },
}

# ── Antigravity (Google OAuth2 with Code Assist) ─────────────────────────────
ANTIGRAVITY_CONFIG: dict[str, Any] = {
    "clientId": settings.ANTIGRAVITY_CLIENT_ID,
    "clientSecret": settings.ANTIGRAVITY_CLIENT_SECRET,
    "authorizeUrl": "https://accounts.google.com/o/oauth2/v2/auth",
    "tokenUrl": "https://oauth2.googleapis.com/token",
    "userInfoUrl": "https://www.googleapis.com/oauth2/v1/userinfo",
    "scopes": [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/cclog",
        "https://www.googleapis.com/auth/experimentsandconfigs",
    ],
    "apiEndpoint": "https://cloudcode-pa.googleapis.com",
    "apiVersion": "v1internal",
    "loadCodeAssistEndpoint": "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
    "onboardUserEndpoint": "https://cloudcode-pa.googleapis.com/v1internal:onboardUser",
    "loadCodeAssistUserAgent": "google-api-nodejs-client/9.15.1",
    "loadCodeAssistApiClient": "google-cloud-sdk vscode_cloudshelleditor/0.1",
    "loadCodeAssistClientMetadata": json.dumps(
        {"ideType": "IDE_UNSPECIFIED", "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}
    ),
}

# ── GitHub Copilot (Device Code Flow) ────────────────────────────────────────
GITHUB_CONFIG: dict[str, Any] = {
    "clientId": settings.GITHUB_CLIENT_ID,
    "deviceCodeUrl": "https://github.com/login/device/code",
    "tokenUrl": "https://github.com/login/oauth/access_token",
    "userInfoUrl": "https://api.github.com/user",
    "scopes": "read:user",
    "apiVersion": "2022-11-28",
    "copilotTokenUrl": "https://api.github.com/copilot_internal/v2/token",
    "userAgent": "GitHubCopilotChat/0.26.7",
    "editorVersion": "vscode/1.85.0",
    "editorPluginVersion": "copilot-chat/0.26.7",
}

# ── Kilo Code (Custom Device Auth Flow) ──────────────────────────────────────
KILOCODE_CONFIG: dict[str, Any] = {
    "apiBaseUrl": "https://api.kilo.ai",
    "initiateUrl": "https://api.kilo.ai/api/device-auth/codes",
    "pollUrlBase": "https://api.kilo.ai/api/device-auth/codes",
}

# ── Cline (Local Callback Flow) ──────────────────────────────────────────────
CLINE_CONFIG: dict[str, Any] = {
    "appBaseUrl": "https://app.cline.bot",
    "apiBaseUrl": "https://api.cline.bot",
    "authorizeUrl": "https://api.cline.bot/api/v1/auth/authorize",
    "tokenExchangeUrl": "https://api.cline.bot/api/v1/auth/token",
    "refreshUrl": "https://api.cline.bot/api/v1/auth/refresh",
}

# ── Kiro (Multiple Auth: Builder ID, IDC, Social, Import) ────────────────────
KIRO_CONFIG: dict[str, Any] = {
    "ssoOidcEndpoint": "https://oidc.us-east-1.amazonaws.com",
    "registerClientUrl": "https://oidc.us-east-1.amazonaws.com/client/register",
    "deviceAuthUrl": "https://oidc.us-east-1.amazonaws.com/device_authorization",
    "tokenUrl": "https://oidc.us-east-1.amazonaws.com/token",
    "startUrl": "https://view.awsapps.com/start",
    "clientName": "kiro-oauth-client",
    "clientType": "public",
    "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"],
    "grantTypes": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
    "issuerUrl": "https://identitycenter.amazonaws.com/ssoins-722374e8c3c8e6c6",
    "socialAuthEndpoint": "https://prod.us-east-1.auth.desktop.kiro.dev",
    "socialLoginUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/login",
    "socialTokenUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/oauth/token",
    "socialRefreshUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken",
    "authMethods": ["builder-id", "idc", "google", "github", "import"],
}

# ── Cursor (Token Import from Local SQLite) ──────────────────────────────────
CURSOR_CONFIG: dict[str, Any] = {
    "apiEndpoint": "https://api2.cursor.sh",
    "chatEndpoint": "/aiserver.v1.ChatService/StreamUnifiedChatWithTools",
    "modelsEndpoint": "/aiserver.v1.AiService/GetDefaultModelNudgeData",
    "api3Endpoint": "https://api3.cursor.sh",
    "agentEndpoint": "https://agent.api5.cursor.sh",
    "agentNonPrivacyEndpoint": "https://agentn.api5.cursor.sh",
    "clientVersion": "3.1.0",
    "clientType": "ide",
    "tokenStoragePaths": {
        "linux": "~/.config/Cursor/User/globalStorage/state.vscdb",
        "macos": "/Users/<user>/Library/Application Support/Cursor/User/globalStorage/state.vscdb",
        "windows": "%APPDATA%\\Cursor\\User\\globalStorage\\state.vscdb",
    },
    "dbKeys": {
        "accessToken": "cursorAuth/accessToken",
        "machineId": "storage.serviceMachineId",
    },
}

# ── Kimi Coding (Device Code Flow) ──────────────────────────────────────────
KIMI_CODING_CONFIG: dict[str, Any] = {
    "clientId": settings.KIMI_CODING_CLIENT_ID,
    "deviceCodeUrl": "https://auth.kimi.com/api/oauth/device_authorization",
    "tokenUrl": "https://auth.kimi.com/api/oauth/token",
}

# ── GitLab Duo (Authorization Code + PKCE, supports PAT) ────────────────────
GITLAB_CONFIG: dict[str, Any] = {
    "defaultBaseUrl": "https://gitlab.com",
    "authorizeUrlPath": "/oauth/authorize",
    "tokenUrlPath": "/oauth/token",
    "userInfoUrlPath": "/api/v4/user",
    "scope": "api read_user",
    "codeChallengeMethod": "S256",
}

# ── CodeBuddy / Tencent (Browser OAuth Polling Flow) ─────────────────────────
CODEBUDDY_CONFIG: dict[str, Any] = {
    "baseUrl": "https://copilot.tencent.com",
    "stateUrl": "https://copilot.tencent.com/v2/plugin/auth/state",
    "tokenUrl": "https://copilot.tencent.com/v2/plugin/auth/token",
    "refreshUrl": "https://copilot.tencent.com/v2/plugin/auth/token/refresh",
    "userAgent": "CLI/2.63.2 CodeBuddy/2.63.2",
    "platform": "CLI",
    "pollInterval": 5000,
}

# ── Provider Name Constants ──────────────────────────────────────────────────
PROVIDERS = {
    "CLAUDE": "claude",
    "CODEX": "codex",
    "GEMINI": "gemini-cli",
    "QWEN": "qwen",
    "QODER": "qoder",
    "IFLOW": "iflow",
    "ANTIGRAVITY": "antigravity",
    "OPENAI": "openai",
    "GITHUB": "github",
    "KIRO": "kiro",
    "CURSOR": "cursor",
    "KIMI_CODING": "kimi-coding",
    "KILOCODE": "kilocode",
    "CLINE": "cline",
    "GITLAB": "gitlab",
    "CODEBUDDY": "codebuddy",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Helper utilities
# ═══════════════════════════════════════════════════════════════════════════════


def _decode_jwt_payload(jwt: str) -> Optional[dict]:
    """Decode JWT payload without verification."""
    try:
        if not jwt or not isinstance(jwt, str):
            return None
        parts = jwt.split(".")
        if len(parts) != 3:
            return None
        b64 = parts[1].replace("-", "+").replace("_", "/")
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        return json.loads(base64.b64decode(b64).decode("utf-8"))
    except Exception:
        return None


def _extract_email_from_token(access_token: str) -> Optional[str]:
    """Extract email from JWT access token."""
    payload = _decode_jwt_payload(access_token)
    if not payload:
        return None
    return payload.get("email") or payload.get("preferred_username") or payload.get("sub")


def _extract_codex_account_info(id_token: str) -> dict:
    """Extract codex account info from id_token."""
    payload = _decode_jwt_payload(id_token)
    if not payload:
        return {}
    chatgpt = payload.get("https://api.openai.com/auth", {})
    return {
        "email": payload.get("email"),
        "chatgptAccountId": chatgpt.get("chatgpt_account_id"),
        "chatgptPlanType": chatgpt.get("chatgpt_plan_type"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. OAuthService — Core OAuth operations
# ═══════════════════════════════════════════════════════════════════════════════


class OAuthService:
    """Core OAuth service with PKCE, device code flow, token exchange, and refresh.

    Ported from src/lib/oauth/services/oauth.js.
    Uses httpx.AsyncClient for all HTTP requests.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    # ── Authorization Code Exchange ──────────────────────────────────────────

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
        content_type: str = "application/x-www-form-urlencoded",
    ) -> dict:
        """Exchange authorization code for tokens.

        Ported from OAuthService.exchangeCode() in oauth.js.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            if content_type == "application/json":
                body = {
                    "grant_type": "authorization_code",
                    "client_id": self.config["clientId"],
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                }
                resp = await client.post(
                    self.config["tokenUrl"],
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    json=body,
                )
            else:
                body = {
                    "grant_type": "authorization_code",
                    "client_id": self.config["clientId"],
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                }
                resp = await client.post(
                    self.config["tokenUrl"],
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    data=body,
                )

        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        return resp.json()

    # ── Device Code Flow ────────────────────────────────────────────────────

    async def request_device_code(
        self,
        provider: str,
        config: dict[str, Any],
        code_challenge: str = "",
        options: Optional[dict] = None,
    ) -> dict:
        """Request a device code from the provider's device code endpoint.

        Ported from the per-provider requestDeviceCode functions.
        """
        handler = _DEVICE_CODE_HANDLERS.get(provider)
        if handler:
            return await handler(config, code_challenge, options or {})

        # Generic fallback
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                config["deviceCodeUrl"],
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "client_id": config["clientId"],
                    "scope": config.get("scopes", config.get("scope", "")),
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Device code request failed: {resp.text}")
        return resp.json()

    async def poll_device_code(
        self,
        provider: str,
        config: dict[str, Any],
        device_code: str,
        code_verifier: str = "",
        extra_data: Optional[dict] = None,
    ) -> dict:
        """Poll the token endpoint using a device code.

        Ported from the per-provider pollToken functions.
        Returns dict with keys: success, tokens (on success), error, pending.
        """
        handler = _POLL_HANDLERS.get(provider)
        if handler:
            result = await handler(config, device_code, code_verifier, extra_data or {})
            return self._normalize_poll_result(result, provider)

        # Generic fallback
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                config["tokenUrl"],
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "client_id": config["clientId"],
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            data = resp.json()

        if data.get("access_token"):
            return {"success": True, "tokens": data}
        error = data.get("error", "unknown")
        return {
            "success": False,
            "error": error,
            "errorDescription": data.get("error_description"),
            "pending": error in ("authorization_pending", "slow_down"),
        }

    def _normalize_poll_result(self, result: dict, provider: str) -> dict:
        """Normalize provider-specific poll result into standard format."""
        if result.get("ok"):
            data = result["data"]
            if data.get("access_token"):
                return {"success": True, "tokens": data}
            error = data.get("error", "")
            return {
                "success": False,
                "error": error,
                "errorDescription": data.get("error_description") or data.get("message"),
                "pending": error in ("authorization_pending", "slow_down"),
            }
        data = result.get("data", {})
        return {
            "success": False,
            "error": data.get("error", "unknown"),
            "errorDescription": data.get("error_description"),
        }

    # ── Token Refresh ───────────────────────────────────────────────────────

    async def refresh_access_token(
        self,
        provider: str,
        config: dict[str, Any],
        refresh_token: str,
        provider_specific_data: Optional[dict] = None,
    ) -> dict:
        """Refresh an expired access token.

        Ported from the per-provider refreshToken functions.
        """
        handler = _REFRESH_HANDLERS.get(provider)
        if handler:
            return await handler(config, refresh_token, provider_specific_data or {})

        # Generic OAuth2 refresh
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                config["tokenUrl"],
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "grant_type": "refresh_token",
                    "client_id": config["clientId"],
                    "refresh_token": refresh_token,
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Token refresh failed: {resp.text}")
        return resp.json()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Provider-Specific Handlers
# ═══════════════════════════════════════════════════════════════════════════════


# ── Codex Proxy Handler ──────────────────────────────────────────────────────
# Ported from src/lib/oauth/services/codex.js
# Codex uses fixed port 1455 for redirect, with a proxy that auto-exchanges
# tokens server-side when the callback arrives.


class CodexHandler:
    """Codex (OpenAI) OAuth handler with proxy support.

    Ported from src/lib/oauth/services/codex.js.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.proxy_sessions: dict[str, dict] = {}

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str) -> str:
        """Build Codex authorization URL.

        Manually constructs query string to ensure space encoding as %20 instead of +.
        """
        params = {
            "response_type": "code",
            "client_id": self.config["clientId"],
            "redirect_uri": redirect_uri,
            "scope": self.config["scope"],
            "code_challenge": code_challenge,
            "code_challenge_method": self.config["codeChallengeMethod"],
            **self.config.get("extraParams", {}),
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.config['authorizeUrl']}?{query}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str, state: str = ""
    ) -> dict:
        """Exchange authorization code for tokens.

        Codex uses application/x-www-form-urlencoded (matches original).
        """
        svc = OAuthService(self.config)
        return await svc.exchange_code(
            code, redirect_uri, code_verifier, content_type="application/x-www-form-urlencoded"
        )

    def start_proxy(
        self, app_port: str, state: str, code_verifier: str, redirect_uri: str
    ) -> dict:
        """Start a proxy session for server-side token exchange.

        Returns dict with success flag and session info.
        The proxy auto-exchanges tokens when the callback arrives.
        """
        self.proxy_sessions[state] = {
            "status": "pending",
            "appPort": app_port,
            "codeVerifier": code_verifier,
            "redirectUri": redirect_uri,
            "connectionId": None,
            "email": None,
        }
        return {"success": True, "serverSide": True}

    def stop_proxy(self, state: str) -> dict:
        """Stop a proxy session."""
        self.proxy_sessions.pop(state, None)
        return {"success": True}

    def poll_proxy_status(self, state: str) -> dict:
        """Poll the status of a proxy session."""
        session = self.proxy_sessions.get(state)
        if not session:
            return {"status": "not_found"}
        return {
            "status": session["status"],
            "connectionId": session.get("connectionId"),
            "email": session.get("email"),
            "error": session.get("error"),
        }

    def extract_account_info(self, tokens: dict) -> dict:
        """Extract account info from Codex tokens."""
        info = _extract_codex_account_info(tokens.get("id_token", ""))
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "email": info.get("email"),
            "providerSpecificData": {
                "chatgptAccountId": info.get("chatgptAccountId"),
                "chatgptPlanType": info.get("chatgptPlanType"),
            },
        }


# ── GitHub Copilot Handler ───────────────────────────────────────────────────
# Ported from src/lib/oauth/services/github.js
# Uses Device Code Flow + fetches Copilot token from GitHub API.


class GitHubHandler:
    """GitHub Copilot OAuth handler.

    Ported from src/lib/oauth/services/github.js.
    Uses device code flow and fetches copilot-specific tokens.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def request_device_code(self) -> dict:
        """Get device code for GitHub authentication.

        POST https://github.com/login/device/code
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.config["deviceCodeUrl"],
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "client_id": self.config["clientId"],
                    "scope": self.config["scopes"],
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Failed to get device code: {resp.text}")
        return resp.json()

    async def poll_token(self, device_code: str) -> dict:
        """Poll for access token using device code.

        POST https://github.com/login/oauth/access_token
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.config["tokenUrl"],
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "client_id": self.config["clientId"],
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            data = resp.json()

        if data.get("access_token"):
            return {"ok": True, "data": data}
        return {"ok": False, "data": data}

    async def get_copilot_token(self, access_token: str) -> dict:
        """Fetch Copilot token from GitHub API.

        GET https://api.github.com/copilot_internal/v2/token
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self.config["copilotTokenUrl"],
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "X-GitHub-Api-Version": self.config["apiVersion"],
                    "User-Agent": self.config["userAgent"],
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Failed to get Copilot token: {resp.text}")
        return resp.json()

    async def get_user_info(self, access_token: str) -> dict:
        """Get user info from GitHub API.

        GET https://api.github.com/user
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self.config["userInfoUrl"],
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "X-GitHub-Api-Version": self.config["apiVersion"],
                    "User-Agent": self.config["userAgent"],
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Failed to get user info: {resp.text}")
        return resp.json()

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        """Map GitHub tokens to standard format."""
        extra = extra or {}
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "providerSpecificData": {
                "copilotToken": extra.get("copilotToken", {}).get("token"),
                "copilotTokenExpiresAt": extra.get("copilotToken", {}).get("expires_at"),
                "githubUserId": extra.get("userInfo", {}).get("id"),
                "githubLogin": extra.get("userInfo", {}).get("login"),
                "githubName": extra.get("userInfo", {}).get("name"),
                "githubEmail": extra.get("userInfo", {}).get("email"),
            },
        }


# ── Kiro Handler ─────────────────────────────────────────────────────────────
# Ported from src/lib/oauth/services/kiro.js
# Supports: AWS Builder ID, AWS IAM Identity Center, Social Login, Token Import


class KiroHandler:
    """Kiro OAuth handler with multiple auth methods.

    Ported from src/lib/oauth/services/kiro.js.
    Supports: AWS Builder ID, IDC, Google/GitHub Social, Token Import.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def register_client(self, region: str = "us-east-1") -> dict:
        """Register OIDC client with AWS SSO.

        Returns clientId and clientSecret for device code flow.
        """
        endpoint = f"https://oidc.{region}.amazonaws.com/client/register"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json={
                    "clientName": self.config["clientName"],
                    "clientType": self.config["clientType"],
                    "scopes": self.config["scopes"],
                    "grantTypes": self.config["grantTypes"],
                    "issuerUrl": self.config["issuerUrl"],
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Failed to register client: {resp.text}")
        data = resp.json()
        return {
            "clientId": data["clientId"],
            "clientSecret": data["clientSecret"],
            "clientSecretExpiresAt": data.get("clientSecretExpiresAt"),
        }

    async def start_device_authorization(
        self, client_id: str, client_secret: str, start_url: str, region: str = "us-east-1"
    ) -> dict:
        """Start device authorization for AWS Builder ID or IDC."""
        endpoint = f"https://oidc.{region}.amazonaws.com/device_authorization"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json={
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "startUrl": start_url,
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Failed to start device authorization: {resp.text}")
        data = resp.json()
        return {
            "deviceCode": data.get("deviceCode"),
            "userCode": data.get("userCode"),
            "verificationUri": data.get("verificationUri"),
            "verificationUriComplete": data.get("verificationUriComplete"),
            "expiresIn": data.get("expiresIn"),
            "interval": data.get("interval", 5),
        }

    async def poll_device_token(
        self, client_id: str, client_secret: str, device_code: str, region: str = "us-east-1"
    ) -> dict:
        """Poll for token using device code (AWS Builder ID/IDC)."""
        endpoint = f"https://oidc.{region}.amazonaws.com/token"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json={
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "deviceCode": device_code,
                    "grantType": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            data = resp.json()

        if not resp.status_code < 400 or data.get("error"):
            return {
                "success": False,
                "error": data.get("error"),
                "errorDescription": data.get("error_description"),
                "pending": data.get("error") in ("authorization_pending", "slow_down"),
            }

        return {
            "success": True,
            "tokens": {
                "accessToken": data.get("accessToken"),
                "refreshToken": data.get("refreshToken"),
                "expiresIn": data.get("expiresIn"),
                "tokenType": data.get("tokenType"),
            },
        }

    def build_social_login_url(
        self, provider: str, code_challenge: str, state: str
    ) -> str:
        """Build Google/GitHub social login URL.

        Uses kiro:// custom protocol as required by AWS Cognito whitelist.
        """
        idp = "Google" if provider == "google" else "Github"
        redirect_uri = "kiro://kiro.kiroAgent/authenticate-success"
        return (
            f"{self.config['socialAuthEndpoint']}/login"
            f"?idp={idp}"
            f"&redirect_uri={redirect_uri}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&state={state}"
            f"&prompt=select_account"
        )

    async def exchange_social_code(self, code: str, code_verifier: str) -> dict:
        """Exchange authorization code for tokens (Social Login).

        Must use same redirect_uri as authorization request.
        """
        redirect_uri = "kiro://kiro.kiroAgent/authenticate-success"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.config['socialAuthEndpoint']}/oauth/token",
                headers={"Content-Type": "application/json"},
                json={
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        data = resp.json()
        return {
            "accessToken": data.get("accessToken"),
            "refreshToken": data.get("refreshToken"),
            "profileArn": data.get("profileArn"),
            "expiresIn": data.get("expiresIn", 3600),
        }

    async def refresh_token(
        self, refresh_token: str, provider_specific_data: Optional[dict] = None
    ) -> dict:
        """Refresh token.

        AWS SSO OIDC refresh (Builder ID or IDC) if clientId/clientSecret present.
        Social auth refresh (Google/GitHub) otherwise.
        """
        psd = provider_specific_data or {}
        client_id = psd.get("clientId")
        client_secret = psd.get("clientSecret")
        region = psd.get("region", "us-east-1")

        # AWS SSO OIDC refresh
        if client_id and client_secret:
            endpoint = f"https://oidc.{region}.amazonaws.com/token"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={"Content-Type": "application/json"},
                    json={
                        "clientId": client_id,
                        "clientSecret": client_secret,
                        "refreshToken": refresh_token,
                        "grantType": "refresh_token",
                    },
                )
            if resp.status_code >= 400:
                raise Exception(f"Token refresh failed: {resp.text}")
            data = resp.json()
            return {
                "accessToken": data.get("accessToken"),
                "refreshToken": data.get("refreshToken") or refresh_token,
                "expiresIn": data.get("expiresIn"),
            }

        # Social auth refresh
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.config['socialAuthEndpoint']}/refreshToken",
                headers={"Content-Type": "application/json"},
                json={"refreshToken": refresh_token},
            )
        if resp.status_code >= 400:
            raise Exception(f"Token refresh failed: {resp.text}")
        data = resp.json()
        return {
            "accessToken": data.get("accessToken"),
            "refreshToken": data.get("refreshToken") or refresh_token,
            "profileArn": data.get("profileArn"),
            "expiresIn": data.get("expiresIn", 3600),
        }

    async def validate_import_token(self, refresh_token: str) -> dict:
        """Validate and import a refresh token.

        Validates format and attempts a refresh to verify.
        """
        if not refresh_token.startswith("aorAAAAAG"):
            raise Exception("Invalid token format. Token should start with aorAAAAAG...")

        try:
            result = await self.refresh_token(refresh_token)
            return {
                "accessToken": result["accessToken"],
                "refreshToken": result.get("refreshToken") or refresh_token,
                "profileArn": result.get("profileArn"),
                "expiresIn": result.get("expiresIn"),
                "authMethod": "imported",
            }
        except Exception as e:
            raise Exception(f"Token validation failed: {e}")

    def extract_email_from_jwt(self, access_token: str) -> Optional[str]:
        """Fetch user email from JWT access token."""
        return _extract_email_from_token(access_token)

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        """Map Kiro tokens to standard format."""
        email = _extract_email_from_token(tokens.get("access_token", ""))
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "email": email,
            "providerSpecificData": {
                "profileArn": tokens.get("profile_arn"),
                "clientId": tokens.get("_clientId"),
                "clientSecret": tokens.get("_clientSecret"),
                "region": tokens.get("_region", "us-east-1"),
                "authMethod": tokens.get("_authMethod", "builder-id"),
                "startUrl": tokens.get("_startUrl", self.config["startUrl"]),
            },
        }


# ── Cursor Handler ───────────────────────────────────────────────────────────
# Ported from src/lib/oauth/services/cursor.js
# Token import from Cursor IDE's local SQLite database.


class CursorHandler:
    """Cursor IDE OAuth handler — token import from local SQLite.

    Ported from src/lib/oauth/services/cursor.js.
    Token location:
      - Linux:   ~/.config/Cursor/User/globalStorage/state.vscdb
      - macOS:   ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb
      - Windows: %APPDATA%\\Cursor\\User\\globalStorage\\state.vscdb
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def auto_import(self) -> dict:
        """Auto-detect and import token from Cursor IDE's local SQLite database.

        Reads cursorAuth/accessToken and storage.serviceMachineId from state.vscdb.
        """
        system = platform.system().lower()
        db_path = os.path.expanduser("~/.config/Cursor/User/globalStorage/state.vscdb")
        if system == "darwin":
            db_path = os.path.expanduser(
                "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
            )
        elif system == "windows":
            appdata = os.environ.get("APPDATA", "")
            db_path = os.path.join(appdata, "Cursor", "User", "globalStorage", "state.vscdb")

        if not os.path.exists(db_path):
            if system == "windows":
                return {"windowsManual": True, "error": "Could not auto-detect on Windows"}
            raise Exception(
                "Could not find Cursor token. Please enter it manually."
            )

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            access_token_key = self.config["dbKeys"]["accessToken"]
            machine_id_key = self.config["dbKeys"]["machineId"]

            cursor.execute(
                "SELECT key, value FROM itemTable WHERE key IN (?, ?)",
                (access_token_key, machine_id_key),
            )
            rows = cursor.fetchall()
            conn.close()

            data = {row[0]: row[1] for row in rows}
            access_token = data.get(access_token_key, "")
            machine_id = data.get(machine_id_key, "")

            if not access_token:
                raise Exception("Access token not found in Cursor database")

            return {
                "found": True,
                "accessToken": access_token,
                "machineId": machine_id,
            }
        except sqlite3.Error as e:
            raise Exception(f"Failed to read Cursor database: {e}")

    async def validate_import_token(
        self, access_token: str, machine_id: str
    ) -> dict:
        """Validate and import a token from Cursor IDE.

        Skips API validation (Cursor uses complex protobuf).
        Token will be validated when actually used.
        """
        if not access_token or not isinstance(access_token, str):
            raise Exception("Access token is required")
        if not machine_id or not isinstance(machine_id, str):
            raise Exception("Machine ID is required")
        if len(access_token) < 50:
            raise Exception("Invalid token format. Token appears too short.")

        # Machine ID format validation (UUID-like)
        import re
        cleaned = machine_id.replace("-", "")
        if not re.match(r"^[a-f0-9]{32,}$", cleaned, re.IGNORECASE):
            raise Exception("Invalid machine ID format. Expected UUID format.")

        return {
            "accessToken": access_token,
            "machineId": machine_id,
            "expiresIn": 86400,
            "authMethod": "imported",
        }

    def build_headers(
        self, access_token: str, machine_id: str, ghost_mode: bool = False
    ) -> dict:
        """Build request headers for Cursor API.

        Includes checksum (jyh cipher) for authentication.
        """
        checksum = self._generate_checksum(machine_id)
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/connect+proto",
            "Connect-Protocol-Version": "1",
            "x-cursor-client-version": self.config["clientVersion"],
            "x-cursor-client-type": self.config["clientType"],
            "x-cursor-client-os": self._detect_os(),
            "x-cursor-client-arch": self._detect_arch(),
            "x-cursor-client-device-type": "desktop",
            "x-cursor-checksum": checksum,
            "x-ghost-mode": "true" if ghost_mode else "false",
        }

    def _generate_checksum(self, machine_id: str) -> str:
        """Generate Cursor checksum (jyh cipher).

        Algorithm: XOR timestamp bytes with rolling key (initial 165), then base64 encode.
        Format: {encoded_timestamp},{machineId}
        """
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        key = 165
        encoded = []
        for ch in timestamp:
            char_code = ord(ch)
            encoded.append(char_code ^ key)
            key = (key + char_code) & 0xFF

        b64 = base64.b64encode(bytes(encoded)).decode("ascii")
        return f"{b64},{machine_id}"

    def _detect_os(self) -> str:
        """Detect OS for headers."""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        if system == "darwin":
            return "macos"
        return "linux"

    def _detect_arch(self) -> str:
        """Detect architecture for headers."""
        machine = platform.machine().lower()
        if machine == "x86_64" or machine == "amd64":
            return "x86_64"
        if machine == "arm64" or machine == "aarch64":
            return "aarch64"
        return machine

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        """Map Cursor tokens to standard format."""
        return {
            "accessToken": tokens.get("accessToken") or tokens.get("access_token"),
            "refreshToken": None,
            "expiresIn": tokens.get("expiresIn", 86400),
            "providerSpecificData": {
                "machineId": tokens.get("machineId"),
                "authMethod": "imported",
            },
        }


# ── GitLab Handler ───────────────────────────────────────────────────────────
# Ported from src/shared/components/GitLabAuthModal.js
# Supports both OAuth (PKCE) and Personal Access Token (PAT) modes.


class GitLabHandler:
    """GitLab Duo OAuth handler with PAT + OAuth dual mode.

    Ported from the original GitLab modal and oauth config.
    Supports both OAuth (Authorization Code + PKCE) and Personal Access Token.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def build_auth_url(
        self,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        base_url: Optional[str] = None,
    ) -> str:
        """Build GitLab authorization URL."""
        base = base_url or self.config["defaultBaseUrl"]
        client_id = self.config.get("clientId", "")
        scope = self.config["scope"].replace(" ", "%20")
        params = "&".join([
            "response_type=code",
            f"client_id={client_id}",
            f"redirect_uri={redirect_uri}",
            f"scope={scope}",
            f"state={state}",
            f"code_challenge={code_challenge}",
            f"code_challenge_method={self.config['codeChallengeMethod']}",
        ])
        return f"{base}{self.config['authorizeUrlPath']}?{params}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
        state: str = "",
        base_url: Optional[str] = None,
    ) -> dict:
        """Exchange authorization code for tokens (OAuth mode)."""
        base = base_url or self.config["defaultBaseUrl"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base}{self.config['tokenUrlPath']}",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"GitLab token exchange failed: {resp.text}")
        return resp.json()

    async def validate_pat(
        self, access_token: str, base_url: Optional[str] = None
    ) -> dict:
        """Validate a Personal Access Token (PAT mode).

        GET /api/v4/user with the PAT as Bearer token.
        Returns user info if valid.
        """
        base = base_url or self.config["defaultBaseUrl"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{base}{self.config['userInfoUrlPath']}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Invalid GitLab PAT: {resp.text}")
        return resp.json()

    async def get_user_info(
        self, access_token: str, base_url: Optional[str] = None
    ) -> dict:
        """Get user info from GitLab."""
        base = base_url or self.config["defaultBaseUrl"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{base}{self.config['userInfoUrlPath']}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        return resp.json() if resp.status_code < 400 else {}

    def map_tokens(
        self, tokens: dict, extra: Optional[dict] = None, auth_method: str = "oauth"
    ) -> dict:
        """Map GitLab tokens to standard format.

        auth_method: 'oauth' or 'pat'
        """
        return {
            "accessToken": tokens.get("access_token") or tokens.get("accessToken"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
            "email": (extra or {}).get("userInfo", {}).get("email"),
            "displayName": (extra or {}).get("userInfo", {}).get("name"),
            "providerSpecificData": {
                "authMethod": auth_method,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Provider-specific request/poll handlers (internal)
#    Used by OAuthService.request_device_code / poll_device_code
# ═══════════════════════════════════════════════════════════════════════════════


async def _request_github_device_code(
    config: dict, code_challenge: str = "", options: Optional[dict] = None
) -> dict:
    """Request GitHub device code. Ported from oauth_providers._request_github_device_code."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["deviceCodeUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={"client_id": config["clientId"], "scope": config["scopes"]},
        )
    if resp.status_code >= 400:
        raise Exception(f"Device code request failed: {resp.text}")
    return resp.json()


async def _poll_github_token(
    config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None
) -> dict:
    """Poll GitHub for token. Ported from oauth_providers._poll_github_token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={
                "client_id": config["clientId"],
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        try:
            data = resp.json()
        except Exception:
            data = {"error": "invalid_response", "error_description": resp.text}
    return {"ok": resp.status_code < 400, "data": data}


async def _request_qwen_device_code(
    config: dict, code_challenge: str = "", options: Optional[dict] = None
) -> dict:
    """Request Qwen device code. Ported from oauth_providers._request_qwen_device_code."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["deviceCodeUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={
                "client_id": config["clientId"],
                "scope": config["scope"],
                "code_challenge": code_challenge,
                "code_challenge_method": config["codeChallengeMethod"],
            },
        )
    if resp.status_code >= 400:
        raise Exception(f"Device code request failed: {resp.text}")
    return resp.json()


async def _poll_qwen_token(
    config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None
) -> dict:
    """Poll Qwen for token. Ported from oauth_providers._poll_qwen_token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": config["clientId"],
                "device_code": device_code,
                "code_verifier": code_verifier,
            },
        )
    return {"ok": resp.status_code < 400, "data": resp.json()}


async def _request_kiro_device_code(
    config: dict, code_challenge: str = "", options: Optional[dict] = None
) -> dict:
    """Request Kiro device code. Ported from oauth_providers._request_kiro_device_code."""
    options = options or {}
    region = (options.get("region") or "").strip() or "us-east-1"
    start_url = (options.get("startUrl") or "").strip() or config["startUrl"]
    auth_method = "idc" if options.get("authMethod") == "idc" else "builder-id"
    register_url = f"https://oidc.{region}.amazonaws.com/client/register"
    device_auth_url = f"https://oidc.{region}.amazonaws.com/device_authorization"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Register client
        reg_resp = await client.post(
            register_url,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={
                "clientName": config["clientName"],
                "clientType": config["clientType"],
                "scopes": config["scopes"],
                "grantTypes": config["grantTypes"],
                "issuerUrl": config["issuerUrl"],
            },
        )
        if reg_resp.status_code >= 400:
            raise Exception(f"Client registration failed: {reg_resp.text}")
        client_info = reg_resp.json()

        # Step 2: Request device authorization
        dev_resp = await client.post(
            device_auth_url,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={
                "clientId": client_info["clientId"],
                "clientSecret": client_info["clientSecret"],
                "startUrl": start_url,
            },
        )
        if dev_resp.status_code >= 400:
            raise Exception(f"Device authorization failed: {dev_resp.text}")
        device_data = dev_resp.json()

    return {
        "device_code": device_data.get("deviceCode"),
        "user_code": device_data.get("userCode"),
        "verification_uri": device_data.get("verificationUri"),
        "verification_uri_complete": device_data.get("verificationUriComplete"),
        "expires_in": device_data.get("expiresIn"),
        "interval": device_data.get("interval", 5),
        "_clientId": client_info["clientId"],
        "_clientSecret": client_info["clientSecret"],
        "_region": region,
        "_authMethod": auth_method,
        "_startUrl": start_url,
    }


async def _poll_kiro_token(
    config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None
) -> dict:
    """Poll Kiro for token. Ported from oauth_providers._poll_kiro_token."""
    region = (extra_data or {}).get("_region", "us-east-1")
    token_url = f"https://oidc.{region}.amazonaws.com/token"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            token_url,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={
                "clientId": (extra_data or {}).get("_clientId"),
                "clientSecret": (extra_data or {}).get("_clientSecret"),
                "deviceCode": device_code,
                "grantType": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        try:
            data = resp.json()
        except Exception:
            data = {"error": "invalid_response", "error_description": resp.text}

    if data.get("accessToken"):
        return {
            "ok": True,
            "data": {
                "access_token": data["accessToken"],
                "refresh_token": data.get("refreshToken"),
                "expires_in": data.get("expiresIn"),
                "profile_arn": data.get("profileArn"),
                "_clientId": (extra_data or {}).get("_clientId"),
                "_clientSecret": (extra_data or {}).get("_clientSecret"),
                "_region": (extra_data or {}).get("_region"),
                "_authMethod": (extra_data or {}).get("_authMethod"),
                "_startUrl": (extra_data or {}).get("_startUrl"),
            },
        }
    return {
        "ok": False,
        "data": {
            "error": data.get("error", "authorization_pending"),
            "error_description": data.get("error_description") or data.get("message"),
        },
    }


async def _request_kimi_coding_device_code(
    config: dict, code_challenge: str = "", options: Optional[dict] = None
) -> dict:
    """Request Kimi Coding device code."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["deviceCodeUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={"client_id": config["clientId"]},
        )
    if resp.status_code >= 400:
        raise Exception(f"Device code request failed: {resp.text}")
    data = resp.json()
    return {
        "device_code": data.get("device_code"),
        "user_code": data.get("user_code"),
        "verification_uri": data.get("verification_uri", "https://www.kimi.com/code/authorize_device"),
        "verification_uri_complete": data.get(
            "verification_uri_complete",
            f"https://www.kimi.com/code/authorize_device?user_code={data.get('user_code', '')}",
        ),
        "expires_in": data.get("expires_in"),
        "interval": data.get("interval", 5),
    }


async def _poll_kimi_coding_token(
    config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None
) -> dict:
    """Poll Kimi Coding for token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": config["clientId"],
                "device_code": device_code,
            },
        )
        try:
            data = resp.json()
        except Exception:
            data = {"error": "invalid_response", "error_description": resp.text}
    return {"ok": resp.status_code < 400, "data": data}


async def _request_kilocode_device_code(
    config: dict, code_challenge: str = "", options: Optional[dict] = None
) -> dict:
    """Request Kilo Code device code. Ported from oauth_providers._request_kilocode_device_code."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["initiateUrl"],
            headers={"Content-Type": "application/json"},
        )
    if resp.status_code == 429:
        raise Exception("Too many pending authorization requests. Please try again later.")
    if resp.status_code >= 400:
        raise Exception(f"Device auth initiation failed: {resp.text}")
    data = resp.json()
    return {
        "device_code": data.get("code"),
        "user_code": data.get("code"),
        "verification_uri": data.get("verificationUrl"),
        "verification_uri_complete": data.get("verificationUrl"),
        "expires_in": data.get("expiresIn", 300),
        "interval": 3,
    }


async def _poll_kilocode_token(
    config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None
) -> dict:
    """Poll Kilo Code for token. Ported from oauth_providers._poll_kilocode_token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{config['pollUrlBase']}/{device_code}")
        if resp.status_code == 202:
            return {"ok": False, "data": {"error": "authorization_pending"}}
        if resp.status_code == 403:
            return {"ok": False, "data": {"error": "access_denied", "error_description": "Authorization denied by user"}}
        if resp.status_code == 410:
            return {"ok": False, "data": {"error": "expired_token", "error_description": "Authorization code expired"}}
        if resp.status_code >= 400:
            return {"ok": False, "data": {"error": "poll_failed", "error_description": f"Poll failed: {resp.status_code}"}}
        data = resp.json()

        if data.get("status") == "approved" and data.get("token"):
            org_id = None
            try:
                profile_resp = await client.get(
                    f"{config['apiBaseUrl']}/api/profile",
                    headers={"Authorization": f"Bearer {data['token']}"},
                )
                if profile_resp.status_code < 400:
                    profile = profile_resp.json()
                    orgs = profile.get("organizations", [])
                    if orgs:
                        org_id = orgs[0].get("id")
            except Exception:
                pass
            return {
                "ok": True,
                "data": {
                    "access_token": data["token"],
                    "_userEmail": data.get("userEmail"),
                    "_orgId": org_id,
                },
            }
        return {"ok": False, "data": {"error": "authorization_pending"}}


async def _request_codebuddy_device_code(
    config: dict, code_challenge: str = "", options: Optional[dict] = None
) -> dict:
    """Request CodeBuddy state/device code."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            config["stateUrl"],
            headers={"User-Agent": config["userAgent"]},
        )
    if resp.status_code >= 400:
        raise Exception(f"CodeBuddy state request failed: {resp.text}")
    data = resp.json()
    return {
        "device_code": data.get("device_code") or data.get("code"),
        "user_code": data.get("user_code"),
        "verification_uri": config["baseUrl"],
        "expires_in": data.get("expires_in", 300),
        "interval": config.get("pollInterval", 5000) / 1000,
        "_requestId": data.get("request_id"),
    }


async def _poll_codebuddy_token(
    config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None
) -> dict:
    """Poll CodeBuddy for token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/json", "User-Agent": config["userAgent"]},
            json={
                "device_code": device_code,
                "request_id": (extra_data or {}).get("_requestId"),
            },
        )
        try:
            data = resp.json()
        except Exception:
            data = {"error": "invalid_response", "error_description": resp.text}

    if resp.status_code == 200 and data.get("access_token"):
        return {
            "ok": True,
            "data": {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in"),
            },
        }
    if data.get("error") in ("authorization_pending", "pending"):
        return {"ok": False, "data": {"error": "authorization_pending"}}
    return {
        "ok": False,
        "data": {
            "error": data.get("error", "unknown"),
            "error_description": data.get("error_description") or data.get("message"),
        },
    }


async def _refresh_codebuddy_token(
    config: dict, refresh_token: str, provider_specific_data: Optional[dict] = None
) -> dict:
    """Refresh CodeBuddy token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["refreshUrl"],
            headers={"Content-Type": "application/json", "User-Agent": config["userAgent"]},
            json={"refresh_token": refresh_token},
        )
    if resp.status_code >= 400:
        raise Exception(f"CodeBuddy token refresh failed: {resp.text}")
    return resp.json()


# ── Handler registries (used by OAuthService) ────────────────────────────────

_DEVICE_CODE_HANDLERS = {
    "github": _request_github_device_code,
    "qwen": _request_qwen_device_code,
    "kiro": _request_kiro_device_code,
    "kimi-coding": _request_kimi_coding_device_code,
    "kilocode": _request_kilocode_device_code,
    "codebuddy": _request_codebuddy_device_code,
}

_POLL_HANDLERS = {
    "github": _poll_github_token,
    "qwen": _poll_qwen_token,
    "kiro": _poll_kiro_token,
    "kimi-coding": _poll_kimi_coding_token,
    "kilocode": _poll_kilocode_token,
    "codebuddy": _poll_codebuddy_token,
}

_REFRESH_HANDLERS = {
    "codebuddy": _refresh_codebuddy_token,
}


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Provider Instance Registry
#    Pre-built handler instances for each provider
# ═══════════════════════════════════════════════════════════════════════════════

claude_service = OAuthService(CLAUDE_CONFIG)
codex_handler = CodexHandler(CODEX_CONFIG)
github_handler = GitHubHandler(GITHUB_CONFIG)
kiro_handler = KiroHandler(KIRO_CONFIG)
cursor_handler = CursorHandler(CURSOR_CONFIG)
gitlab_handler = GitLabHandler(GITLAB_CONFIG)
gemini_service = OAuthService(GEMINI_CONFIG)
qwen_service = OAuthService(QWEN_CONFIG)
iflow_service = OAuthService(IFLOW_CONFIG)
antigravity_service = OAuthService(ANTIGRAVITY_CONFIG)
kilocode_service = OAuthService(KILOCODE_CONFIG)
cline_service = OAuthService(CLINE_CONFIG)
kimi_coding_service = OAuthService(KIMI_CODING_CONFIG)
codebuddy_service = OAuthService(CODEBUDDY_CONFIG)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Convenience Functions (module-level API)
#    Used by routers/oauth.py and other modules
# ═══════════════════════════════════════════════════════════════════════════════

# Provider config lookup table
_PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "claude": CLAUDE_CONFIG,
    "codex": CODEX_CONFIG,
    "openai": OPENAI_CONFIG,
    "gemini-cli": GEMINI_CONFIG,
    "qwen": QWEN_CONFIG,
    "qoder": QODER_CONFIG,
    "iflow": IFLOW_CONFIG,
    "antigravity": ANTIGRAVITY_CONFIG,
    "github": GITHUB_CONFIG,
    "kiro": KIRO_CONFIG,
    "cursor": CURSOR_CONFIG,
    "kimi-coding": KIMI_CODING_CONFIG,
    "kilocode": KILOCODE_CONFIG,
    "cline": CLINE_CONFIG,
    "gitlab": GITLAB_CONFIG,
    "codebuddy": CODEBUDDY_CONFIG,
}


def get_provider_config(provider_name: str) -> dict[str, Any]:
    """Get OAuth config for a provider by name."""
    config = _PROVIDER_CONFIGS.get(provider_name)
    if not config:
        raise ValueError(f"Unknown provider: {provider_name}")
    return config


async def exchange_code(
    provider: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    content_type: str = "application/x-www-form-urlencoded",
) -> dict:
    """Exchange authorization code for tokens (convenience wrapper)."""
    config = get_provider_config(provider)
    svc = OAuthService(config)
    return await svc.exchange_code(code, redirect_uri, code_verifier, content_type)


async def request_device_code(
    provider: str,
    config: Optional[dict] = None,
    code_challenge: str = "",
    options: Optional[dict] = None,
) -> dict:
    """Request a device code (convenience wrapper)."""
    if config is None:
        config = get_provider_config(provider)
    svc = OAuthService(config)
    return await svc.request_device_code(provider, config, code_challenge, options)


async def poll_device_code(
    provider: str,
    device_code: str,
    config: Optional[dict] = None,
    code_verifier: str = "",
    extra_data: Optional[dict] = None,
) -> dict:
    """Poll for device code token (convenience wrapper)."""
    if config is None:
        config = get_provider_config(provider)
    svc = OAuthService(config)
    return await svc.poll_device_code(provider, config, device_code, code_verifier, extra_data)


async def refresh_access_token(
    provider: str,
    refresh_token: str,
    provider_specific_data: Optional[dict] = None,
) -> dict:
    """Refresh an access token (convenience wrapper)."""
    config = get_provider_config(provider)
    svc = OAuthService(config)
    return await svc.refresh_access_token(provider, config, refresh_token, provider_specific_data)
