"""OAuth Provider Configurations and Handlers.

Centralized DRY approach for all OAuth providers, ported from the original
Next.js implementation. Each provider has a different flow:
  - Authorization Code + PKCE: claude, codex
  - Authorization Code (no PKCE): gemini-cli, antigravity, iflow
  - Device Code Flow: github, qwen, kiro, kimi-coding, kilocode
  - Special: cursor (import_token), cline (base64-encoded token callback)
"""

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import settings
from app.utils.pkce import generate_pkce

logger = logging.getLogger(__name__)

# ── OAuth Configuration Constants ────────────────────────────────────────────

CLAUDE_CONFIG = {
    "clientId": settings.CLAUDE_CLIENT_ID,
    "authorizeUrl": "https://claude.ai/oauth/authorize",
    "tokenUrl": "https://api.anthropic.com/v1/oauth/token",
    "scopes": ["org:create_api_key", "user:profile", "user:inference"],
    "codeChallengeMethod": "S256",
}

CODEX_CONFIG = {
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

GEMINI_CONFIG = {
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

QWEN_CONFIG = {
    "clientId": settings.QWEN_CLIENT_ID,
    "deviceCodeUrl": "https://chat.qwen.ai/api/v1/oauth2/device/code",
    "tokenUrl": "https://chat.qwen.ai/api/v1/oauth2/token",
    "scope": "openid profile email model.completion",
    "codeChallengeMethod": "S256",
}

QODER_CONFIG = {
    "openApiBaseUrl": "https://openapi.qoder.sh",
    "centerBaseUrl": "https://center.qoder.sh",
    "chatBaseUrl": "https://api3.qoder.sh",
    "deviceTokenUrl": "https://openapi.qoder.sh/api/v1/deviceToken/poll",
    "refreshUrl": "https://center.qoder.sh/algo/api/v3/user/refresh_token",
    "userInfoUrl": "https://openapi.qoder.sh/api/v1/userinfo",
    "quotaUsageUrl": "https://openapi.qoder.sh/api/v2/quota/usage",
    "loginUrl": "https://qoder.com/device/selectAccounts",
}

IFLOW_CONFIG = {
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

ANTIGRAVITY_CONFIG = {
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

GITHUB_CONFIG = {
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

KIRO_CONFIG = {
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

CURSOR_CONFIG = {
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

KIMI_CODING_CONFIG = {
    "clientId": settings.KIMI_CODING_CLIENT_ID,
    "deviceCodeUrl": "https://auth.kimi.com/api/oauth/device_authorization",
    "tokenUrl": "https://auth.kimi.com/api/oauth/token",
}

KILOCODE_CONFIG = {
    "apiBaseUrl": "https://api.kilo.ai",
    "initiateUrl": "https://api.kilo.ai/api/device-auth/codes",
    "pollUrlBase": "https://api.kilo.ai/api/device-auth/codes",
}

CLINE_CONFIG = {
    "appBaseUrl": "https://app.cline.bot",
    "apiBaseUrl": "https://api.cline.bot",
    "authorizeUrl": "https://api.cline.bot/api/v1/auth/authorize",
    "tokenExchangeUrl": "https://api.cline.bot/api/v1/auth/token",
    "refreshUrl": "https://api.cline.bot/api/v1/auth/refresh",
}

GITLAB_CONFIG = {
    "defaultBaseUrl": "https://gitlab.com",
    "authorizeUrlPath": "/oauth/authorize",
    "tokenUrlPath": "/oauth/token",
    "userInfoUrlPath": "/api/v4/user",
    "scope": "api read_user",
    "codeChallengeMethod": "S256",
}

CODEBUDDY_CONFIG = {
    "baseUrl": "https://copilot.tencent.com",
    "stateUrl": "https://copilot.tencent.com/v2/plugin/auth/state",
    "tokenUrl": "https://copilot.tencent.com/v2/plugin/auth/token",
    "refreshUrl": "https://copilot.tencent.com/v2/plugin/auth/token/refresh",
    "userAgent": "CLI/2.63.2 CodeBuddy/2.63.2",
    "platform": "CLI",
    "pollInterval": 5000,
}

# ── Provider Flow Definitions ────────────────────────────────────────────────
# Each provider has: flowType, config, and handler methods

PROVIDERS: dict[str, dict[str, Any]] = {}

# ── Helper functions ─────────────────────────────────────────────────────────


def _decode_jwt_payload(jwt: str) -> Optional[dict]:
    """Decode JWT access token payload without verification."""
    try:
        if not jwt or not isinstance(jwt, str):
            return None
        parts = jwt.split(".")
        if len(parts) != 3:
            return None
        base64_str = parts[1].replace("-", "+").replace("_", "/")
        padding = (4 - len(base64_str) % 4) % 4
        base64_str += "=" * padding
        return json.loads(base64.b64decode(base64_str).decode("utf-8"))
    except Exception:
        return None


def _extract_email_from_access_token(access_token: str) -> Optional[str]:
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


# ── Provider Handlers ────────────────────────────────────────────────────────


def _build_claude_auth_url(config: dict, redirect_uri: str, state: str, code_challenge: str) -> str:
    params = "&".join([
        "code=true",
        f"client_id={config['clientId']}",
        "response_type=code",
        f"redirect_uri={redirect_uri}",
        f"scope={'%20'.join(config['scopes'])}",
        f"code_challenge={code_challenge}",
        f"code_challenge_method={config['codeChallengeMethod']}",
        f"state={state}",
    ])
    return f"{config['authorizeUrl']}?{params}"


async def _exchange_claude(config: dict, code: str, redirect_uri: str, code_verifier: str, state: str) -> dict:
    auth_code = code
    code_state = ""
    if "#" in auth_code:
        parts = auth_code.split("#")
        auth_code = parts[0]
        code_state = parts[1] if len(parts) > 1 else ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={
                "code": auth_code,
                "state": code_state or state,
                "grant_type": "authorization_code",
                "client_id": config["clientId"],
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        return resp.json()


def _map_claude_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
    }


def _build_codex_auth_url(config: dict, redirect_uri: str, state: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": config["clientId"],
        "redirect_uri": redirect_uri,
        "scope": config["scope"],
        "code_challenge": code_challenge,
        "code_challenge_method": config["codeChallengeMethod"],
        **config["extraParams"],
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{config['authorizeUrl']}?{query}"


async def _exchange_codex(config: dict, code: str, redirect_uri: str, code_verifier: str, state: str = "") -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={
                "grant_type": "authorization_code",
                "client_id": config["clientId"],
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        return resp.json()


def _map_codex_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    info = _extract_codex_account_info(tokens.get("id_token", ""))
    mapped = {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
    }
    if info.get("email"):
        mapped["email"] = info["email"]
    if info.get("chatgptAccountId") or info.get("chatgptPlanType"):
        mapped["providerSpecificData"] = {
            "chatgptAccountId": info.get("chatgptAccountId"),
            "chatgptPlanType": info.get("chatgptPlanType"),
        }
    return mapped


def _build_gemini_auth_url(config: dict, redirect_uri: str, state: str) -> str:
    params = "&".join([
        f"client_id={config['clientId']}",
        "response_type=code",
        f"redirect_uri={redirect_uri}",
        f"scope={'%20'.join(config['scopes'])}",
        f"state={state}",
        "access_type=offline",
        "prompt=consent",
    ])
    return f"{config['authorizeUrl']}?{params}"


async def _exchange_gemini(config: dict, code: str, redirect_uri: str, code_verifier: str = "", state: str = "") -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={
                "grant_type": "authorization_code",
                "client_id": config["clientId"],
                "client_secret": config["clientSecret"],
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        return resp.json()


async def _post_exchange_gemini(tokens: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        user_resp = await client.get(
            f"{GEMINI_CONFIG['userInfoUrl']}?alt=json",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_info = user_resp.json() if user_resp.status_code < 400 else {}

        project_id = ""
        try:
            proj_resp = await client.post(
                "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}",
                    "Content-Type": "application/json",
                },
                json={"metadata": {"ideType": 9, "platform": 3, "pluginType": 2}, "mode": 1},
            )
            if proj_resp.status_code < 400:
                data = proj_resp.json()
                project_id = data.get("cloudaicompanionProject", {})
                if isinstance(project_id, dict):
                    project_id = project_id.get("id", "")
        except Exception as e:
            logger.info(f"Failed to fetch project ID: {e}")

        return {"userInfo": user_info, "projectId": project_id}


def _map_gemini_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
        "email": (extra or {}).get("userInfo", {}).get("email"),
        "projectId": (extra or {}).get("projectId"),
    }


def _build_antigravity_auth_url(config: dict, redirect_uri: str, state: str) -> str:
    params = "&".join([
        f"client_id={config['clientId']}",
        "response_type=code",
        f"redirect_uri={redirect_uri}",
        f"scope={'%20'.join(config['scopes'])}",
        f"state={state}",
        "access_type=offline",
        "prompt=consent",
    ])
    return f"{config['authorizeUrl']}?{params}"


async def _exchange_antigravity(config: dict, code: str, redirect_uri: str, code_verifier: str = "", state: str = "") -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={
                "grant_type": "authorization_code",
                "client_id": config["clientId"],
                "client_secret": config["clientSecret"],
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        return resp.json()


async def _post_exchange_antigravity(tokens: dict) -> dict:
    load_headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Content-Type": "application/json",
        "User-Agent": ANTIGRAVITY_CONFIG["loadCodeAssistUserAgent"],
        "X-Goog-Api-Client": ANTIGRAVITY_CONFIG["loadCodeAssistApiClient"],
        "Client-Metadata": ANTIGRAVITY_CONFIG["loadCodeAssistClientMetadata"],
        "x-request-source": "local",
    }
    metadata = {"ideType": "IDE_UNSPECIFIED", "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        user_resp = await client.get(
            f"{ANTIGRAVITY_CONFIG['userInfoUrl']}?alt=json",
            headers={"Authorization": f"Bearer {tokens['access_token']}", "x-request-source": "local"},
        )
        user_info = user_resp.json() if user_resp.status_code < 400 else {}

        project_id = ""
        tier_id = "legacy-tier"
        try:
            load_resp = await client.post(
                ANTIGRAVITY_CONFIG["loadCodeAssistEndpoint"],
                headers=load_headers,
                json={"metadata": metadata},
            )
            if load_resp.status_code < 400:
                data = load_resp.json()
                project_id = data.get("cloudaicompanionProject", {})
                if isinstance(project_id, dict):
                    project_id = project_id.get("id", "")
                if isinstance(data.get("allowedTiers"), list):
                    for tier in data["allowedTiers"]:
                        if tier.get("isDefault") and tier.get("id"):
                            tier_id = tier["id"].strip()
                            break
        except Exception as e:
            logger.info(f"Failed to load code assist: {e}")

        # Fire-and-forget onboarding
        if project_id:
            try:
                for _ in range(3):
                    onboard_resp = await client.post(
                        ANTIGRAVITY_CONFIG["onboardUserEndpoint"],
                        headers=load_headers,
                        json={"tierId": tier_id, "metadata": metadata},
                    )
                    if onboard_resp.status_code < 400:
                        result = onboard_resp.json()
                        if result.get("done"):
                            break
            except Exception:
                pass

        return {"userInfo": user_info, "projectId": project_id}


def _map_antigravity_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
        "email": (extra or {}).get("userInfo", {}).get("email"),
        "projectId": (extra or {}).get("projectId"),
    }


def _build_iflow_auth_url(config: dict, redirect_uri: str, state: str) -> str:
    params = "&".join([
        f"loginMethod={config['extraParams']['loginMethod']}",
        f"type={config['extraParams']['type']}",
        f"redirect={redirect_uri}",
        f"state={state}",
        f"client_id={config['clientId']}",
    ])
    return f"{config['authorizeUrl']}?{params}"


async def _exchange_iflow(config: dict, code: str, redirect_uri: str, code_verifier: str = "", state: str = "") -> dict:
    basic_auth = base64.b64encode(f"{config['clientId']}:{config['clientSecret']}".encode()).decode()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["tokenUrl"],
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Authorization": f"Basic {basic_auth}",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": config["clientId"],
                "client_secret": config["clientSecret"],
            },
        )
        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        return resp.json()


async def _post_exchange_iflow(tokens: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{IFLOW_CONFIG['userInfoUrl']}?accessToken={tokens['access_token']}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code >= 400:
            raise Exception(f"Failed to fetch user info: {resp.text}")
        result = resp.json()
        if not result.get("success"):
            raise Exception(f"User info request failed: {result.get('message', 'Unknown error')}")
        user_info = result.get("data", {})
        if not user_info.get("apiKey", "").strip():
            raise Exception("Empty API key returned from iFlow")
        email = (user_info.get("email") or user_info.get("phone") or "").strip()
        if not email:
            raise Exception("Missing account email/phone in user info")
        return {"userInfo": user_info}


def _map_iflow_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    user_info = (extra or {}).get("userInfo", {})
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "apiKey": user_info.get("apiKey"),
        "email": user_info.get("email") or user_info.get("phone"),
        "displayName": user_info.get("nickname") or user_info.get("name"),
    }


# ── Device Code Flow Providers ───────────────────────────────────────────────


async def _request_github_device_code(config: dict, code_challenge: str = "", options: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["deviceCodeUrl"],
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={"client_id": config["clientId"], "scope": config["scopes"]},
        )
        if resp.status_code >= 400:
            raise Exception(f"Device code request failed: {resp.text}")
        return resp.json()


async def _poll_github_token(config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None) -> dict:
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


async def _post_exchange_github(tokens: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        copilot_resp = await client.get(
            GITHUB_CONFIG["copilotTokenUrl"],
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Accept": "application/json",
                "X-GitHub-Api-Version": GITHUB_CONFIG["apiVersion"],
                "User-Agent": GITHUB_CONFIG["userAgent"],
            },
        )
        copilot_token = copilot_resp.json() if copilot_resp.status_code < 400 else {}

        user_resp = await client.get(
            GITHUB_CONFIG["userInfoUrl"],
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Accept": "application/json",
                "X-GitHub-Api-Version": GITHUB_CONFIG["apiVersion"],
                "User-Agent": GITHUB_CONFIG["userAgent"],
            },
        )
        user_info = user_resp.json() if user_resp.status_code < 400 else {}

        return {"copilotToken": copilot_token, "userInfo": user_info}


def _map_github_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
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


async def _request_qwen_device_code(config: dict, code_challenge: str = "", options: Optional[dict] = None) -> dict:
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


async def _poll_qwen_token(config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None) -> dict:
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


def _map_qwen_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "providerSpecificData": {"resourceUrl": tokens.get("resource_url")},
    }


async def _request_kiro_device_code(config: dict, code_challenge: str = "", options: Optional[dict] = None) -> dict:
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


async def _poll_kiro_token(config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None) -> dict:
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


def _map_kiro_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    email = _extract_email_from_access_token(tokens.get("access_token", ""))
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
            "startUrl": tokens.get("_startUrl", KIRO_CONFIG["startUrl"]),
        },
    }


async def _request_kimi_coding_device_code(config: dict, code_challenge: str = "", options: Optional[dict] = None) -> dict:
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


async def _poll_kimi_coding_token(config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None) -> dict:
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


def _map_kimi_coding_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
    }


async def _request_kilocode_device_code(config: dict, code_challenge: str = "", options: Optional[dict] = None) -> dict:
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


async def _poll_kilocode_token(config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None) -> dict:
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
            return {"ok": True, "data": {"access_token": data["token"], "_userEmail": data.get("userEmail"), "_orgId": org_id}}
        return {"ok": False, "data": {"error": "authorization_pending"}}


def _map_kilocode_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    result = {
        "accessToken": tokens.get("access_token"),
        "refreshToken": None,
        "expiresIn": None,
        "email": tokens.get("_userEmail"),
    }
    if tokens.get("_orgId"):
        result["providerSpecificData"] = {"orgId": tokens["_orgId"]}
    return result


# ── Special Flow Providers ───────────────────────────────────────────────────

def _map_cursor_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("accessToken"),
        "refreshToken": None,
        "expiresIn": tokens.get("expiresIn", 86400),
        "providerSpecificData": {
            "machineId": tokens.get("machineId"),
            "authMethod": "imported",
        },
    }


def _build_cline_auth_url(config: dict, redirect_uri: str, state: str = "") -> str:
    params = "&".join([
        "client_type=extension",
        f"callback_url={redirect_uri}",
        f"redirect_uri={redirect_uri}",
    ])
    return f"{config['authorizeUrl']}?{params}"


async def _exchange_cline(config: dict, code: str, redirect_uri: str, code_verifier: str = "", state: str = "") -> dict:
    try:
        # Cline encodes token data as base64
        base64_str = code
        padding = (4 - len(base64_str) % 4) % 4
        if padding != 4:
            base64_str += "=" * padding
        decoded = base64.b64decode(base64_str).decode("utf-8")
        last_brace = decoded.rfind("}")
        if last_brace == -1:
            raise Exception("No JSON found in decoded code")
        token_data = json.loads(decoded[: last_brace + 1])
        return {
            "access_token": token_data.get("accessToken"),
            "refresh_token": token_data.get("refreshToken"),
            "email": token_data.get("email"),
            "firstName": token_data.get("firstName"),
            "lastName": token_data.get("lastName"),
            "expires_at": token_data.get("expiresAt"),
        }
    except Exception:
        # Fallback to token exchange endpoint
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                config["tokenExchangeUrl"],
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_type": "extension",
                    "redirect_uri": redirect_uri,
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"Cline token exchange failed: {resp.text}")
            data = resp.json()
            inner = data.get("data", data)
            return {
                "access_token": inner.get("accessToken"),
                "refresh_token": inner.get("refreshToken"),
                "email": inner.get("userInfo", {}).get("email", ""),
                "expires_at": inner.get("expiresAt"),
            }


def _map_cline_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    expires_in = None
    if tokens.get("expires_at"):
        try:
            exp = datetime.fromisoformat(tokens["expires_at"].replace("Z", "+00:00"))
            expires_in = int((exp - datetime.now(timezone.utc)).total_seconds())
        except Exception:
            expires_in = 3600
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": expires_in or 3600,
        "email": tokens.get("email"),
        "providerSpecificData": {
            "firstName": tokens.get("firstName"),
            "lastName": tokens.get("lastName"),
        },
    }


# ── GitLab OAuth (Authorization Code + PKCE) ────────────────────────────────


def _build_gitlab_auth_url(config: dict, redirect_uri: str, state: str, code_challenge: str) -> str:
    base_url = config.get("defaultBaseUrl", "https://gitlab.com")
    params = "&".join([
        "response_type=code",
        f"client_id={config.get('clientId', '')}",
        f"redirect_uri={redirect_uri}",
        f"scope={config['scope'].replace(' ', '%20')}",
        f"state={state}",
        f"code_challenge={code_challenge}",
        f"code_challenge_method={config['codeChallengeMethod']}",
    ])
    return f"{base_url}{config['authorizeUrlPath']}?{params}"


async def _exchange_gitlab(config: dict, code: str, redirect_uri: str, code_verifier: str, state: str) -> dict:
    base_url = config.get("defaultBaseUrl", "https://gitlab.com")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}{config['tokenUrlPath']}",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
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


def _map_gitlab_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
        "email": (extra or {}).get("userInfo", {}).get("email"),
        "displayName": (extra or {}).get("userInfo", {}).get("name"),
    }


async def _post_exchange_gitlab(tokens: dict) -> dict:
    base_url = GITLAB_CONFIG.get("defaultBaseUrl", "https://gitlab.com")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}{GITLAB_CONFIG['userInfoUrlPath']}",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_info = resp.json() if resp.status_code < 400 else {}
        return {"userInfo": user_info}


# ── CodeBuddy OAuth (Polling Flow) ──────────────────────────────────────────


async def _request_codebuddy_device_code(config: dict, code_challenge: str = "", options: Optional[dict] = None) -> dict:
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


async def _poll_codebuddy_token(config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None) -> dict:
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


def _map_codebuddy_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
    }


async def _refresh_codebuddy_token(config: dict, refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["refreshUrl"],
            headers={"Content-Type": "application/json", "User-Agent": config["userAgent"]},
            json={"refresh_token": refresh_token},
        )
        if resp.status_code >= 400:
            raise Exception(f"CodeBuddy token refresh failed: {resp.text}")
        return resp.json()


# ── Qoder Handlers ──────────────────────────────────────────────────────────

async def _request_qoder_device_code(config: dict, code_challenge: str = "", options: Optional[dict] = None) -> dict:
    """Request device code for Qoder using custom device flow."""
    from app.services.qoder.auth import initiate_device_flow

    flow = initiate_device_flow()
    # Match the device_code shape the OAuthModal expects
    return {
        "device_code": flow["nonce"],
        "user_code": flow["nonce"][:8].upper(),
        "verification_uri": config["loginUrl"],
        "verification_uri_complete": flow["verification_uri_complete"],
        "expires_in": 300,
        "interval": 2,
        "codeVerifier": flow["code_verifier"],
        "_qoderNonce": flow["nonce"],
        "_qoderMachineId": flow["machine_id"],
    }


async def _poll_qoder_token(config: dict, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None) -> dict:
    """Poll for Qoder device token."""
    from app.services.qoder.auth import poll_device_token

    nonce = device_code or (extra_data or {}).get("_qoderNonce")
    verifier = code_verifier or (extra_data or {}).get("_qoderVerifier")

    if not nonce or not verifier:
        return {
            "ok": False,
            "data": {"error": "invalid_request", "error_description": "Missing nonce/verifier"},
        }

    try:
        result = await poll_device_token(nonce=nonce, code_verifier=verifier)
    except Exception as err:
        return {
            "ok": False,
            "data": {"error": "poll_failed", "error_description": str(err)},
        }

    if result.get("status") == "ok":
        return {
            "ok": True,
            "data": {
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token"),
                "expires_in": result.get("expires_in"),
                "user_id": result.get("user_id"),
                "display_name": result.get("display_name"),
                "email": result.get("email"),
            },
        }

    return {"ok": False, "data": {"error": "authorization_pending"}}


def _map_qoder_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    """Map Qoder tokens to standard format."""
    psd = {}
    if tokens.get("user_id"):
        psd["userId"] = tokens["user_id"]
    if extra and extra.get("_qoderMachineId"):
        psd["machineId"] = extra["_qoderMachineId"]

    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "email": tokens.get("email"),
        "displayName": tokens.get("display_name"),
        "providerSpecificData": psd if psd else None,
    }


async def _refresh_qoder_token(config: dict, refresh_token: str) -> dict:
    """Refresh Qoder token (currently returns 403 for device tokens)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config["refreshUrl"],
            headers={"Content-Type": "application/json"},
            json={"refresh_token": refresh_token},
        )
        if resp.status_code >= 400:
            raise Exception(f"Qoder token refresh failed: {resp.text}")
        return resp.json()


# ── Provider Registry ────────────────────────────────────────────────────────

PROVIDERS = {
    "claude": {
        "config": CLAUDE_CONFIG,
        "flowType": "authorization_code_pkce",
        "buildAuthUrl": _build_claude_auth_url,
        "exchangeToken": _exchange_claude,
        "mapTokens": _map_claude_tokens,
    },
    "codex": {
        "config": CODEX_CONFIG,
        "flowType": "authorization_code_pkce",
        "buildAuthUrl": _build_codex_auth_url,
        "exchangeToken": _exchange_codex,
        "mapTokens": _map_codex_tokens,
    },
    "gemini-cli": {
        "config": GEMINI_CONFIG,
        "flowType": "authorization_code",
        "buildAuthUrl": _build_gemini_auth_url,
        "exchangeToken": _exchange_gemini,
        "postExchange": _post_exchange_gemini,
        "mapTokens": _map_gemini_tokens,
    },
    "antigravity": {
        "config": ANTIGRAVITY_CONFIG,
        "flowType": "authorization_code",
        "buildAuthUrl": _build_antigravity_auth_url,
        "exchangeToken": _exchange_antigravity,
        "postExchange": _post_exchange_antigravity,
        "mapTokens": _map_antigravity_tokens,
    },
    "iflow": {
        "config": IFLOW_CONFIG,
        "flowType": "authorization_code",
        "buildAuthUrl": _build_iflow_auth_url,
        "exchangeToken": _exchange_iflow,
        "postExchange": _post_exchange_iflow,
        "mapTokens": _map_iflow_tokens,
    },
    "qwen": {
        "config": QWEN_CONFIG,
        "flowType": "device_code",
        "requestDeviceCode": _request_qwen_device_code,
        "pollToken": _poll_qwen_token,
        "mapTokens": _map_qwen_tokens,
    },
    "github": {
        "config": GITHUB_CONFIG,
        "flowType": "device_code",
        "requestDeviceCode": _request_github_device_code,
        "pollToken": _poll_github_token,
        "postExchange": _post_exchange_github,
        "mapTokens": _map_github_tokens,
    },
    "kiro": {
        "config": KIRO_CONFIG,
        "flowType": "device_code",
        "requestDeviceCode": _request_kiro_device_code,
        "pollToken": _poll_kiro_token,
        "mapTokens": _map_kiro_tokens,
    },
    "cursor": {
        "config": CURSOR_CONFIG,
        "flowType": "import_token",
        "mapTokens": _map_cursor_tokens,
    },
    "kimi-coding": {
        "config": KIMI_CODING_CONFIG,
        "flowType": "device_code",
        "requestDeviceCode": _request_kimi_coding_device_code,
        "pollToken": _poll_kimi_coding_token,
        "mapTokens": _map_kimi_coding_tokens,
    },
    "kilocode": {
        "config": KILOCODE_CONFIG,
        "flowType": "device_code",
        "requestDeviceCode": _request_kilocode_device_code,
        "pollToken": _poll_kilocode_token,
        "mapTokens": _map_kilocode_tokens,
    },
    "cline": {
        "config": CLINE_CONFIG,
        "flowType": "authorization_code",
        "buildAuthUrl": _build_cline_auth_url,
        "exchangeToken": _exchange_cline,
        "mapTokens": _map_cline_tokens,
    },
    "gitlab": {
        "config": GITLAB_CONFIG,
        "flowType": "authorization_code_pkce",
        "buildAuthUrl": _build_gitlab_auth_url,
        "exchangeToken": _exchange_gitlab,
        "postExchange": _post_exchange_gitlab,
        "mapTokens": _map_gitlab_tokens,
    },
    "codebuddy": {
        "config": CODEBUDDY_CONFIG,
        "flowType": "polling",
        "requestDeviceCode": _request_codebuddy_device_code,
        "pollToken": _poll_codebuddy_token,
        "mapTokens": _map_codebuddy_tokens,
        "refreshToken": _refresh_codebuddy_token,
    },
    "qoder": {
        "config": QODER_CONFIG,
        "flowType": "device_code",
        "requestDeviceCode": _request_qoder_device_code,
        "pollToken": _poll_qoder_token,
        "mapTokens": _map_qoder_tokens,
        "refreshToken": _refresh_qoder_token,
    },
}


def get_provider(name: str) -> dict:
    """Get provider handler by name."""
    provider = PROVIDERS.get(name)
    if not provider:
        raise ValueError(f"Unknown provider: {name}")
    return provider


def generate_auth_data(provider_name: str, redirect_uri: str, meta: Optional[dict] = None) -> dict:
    """Generate auth data for a provider.

    Returns dict with: authUrl, state, codeVerifier, codeChallenge, redirectUri, flowType
    """
    provider = get_provider(provider_name)
    pkce = generate_pkce()

    auth_url = None
    if provider["flowType"] == "device_code":
        auth_url = None
    elif provider["flowType"] == "authorization_code_pkce":
        auth_url = provider["buildAuthUrl"](provider["config"], redirect_uri, pkce["state"], pkce["codeChallenge"])
    elif provider["flowType"] in ("authorization_code",):
        auth_url = provider["buildAuthUrl"](provider["config"], redirect_uri, pkce["state"])
    # import_token has no auth_url

    return {
        "authUrl": auth_url,
        "state": pkce["state"],
        "codeVerifier": pkce["codeVerifier"],
        "codeChallenge": pkce["codeChallenge"],
        "redirectUri": redirect_uri,
        "flowType": provider["flowType"],
    }


async def exchange_tokens(
    provider_name: str,
    code: str,
    redirect_uri: str,
    code_verifier: str = "",
    state: str = "",
    meta: Optional[dict] = None,
) -> dict:
    """Exchange code for tokens and return mapped token data."""
    provider = get_provider(provider_name)

    tokens = await provider["exchangeToken"](
        provider["config"], code, redirect_uri, code_verifier, state
    )

    extra = None
    if provider.get("postExchange"):
        extra = await provider["postExchange"](tokens)

    return provider["mapTokens"](tokens, extra)


async def request_device_code(
    provider_name: str,
    code_challenge: str = "",
    options: Optional[dict] = None,
) -> dict:
    """Request device code for device_code flow providers."""
    provider = get_provider(provider_name)
    if provider["flowType"] not in ("device_code", "polling"):
        raise ValueError(f"Provider {provider_name} does not support device code flow")
    return await provider["requestDeviceCode"](provider["config"], code_challenge, options or {})


async def poll_for_token(
    provider_name: str,
    device_code: str,
    code_verifier: str = "",
    extra_data: Optional[dict] = None,
) -> dict:
    """Poll for token for device_code flow providers.

    Returns dict with: success, tokens (if success), error, pending
    """
    provider = get_provider(provider_name)
    if provider["flowType"] not in ("device_code", "polling"):
        raise ValueError(f"Provider {provider_name} does not support device code flow")

    result = await provider["pollToken"](provider["config"], device_code, code_verifier, extra_data)

    if result.get("ok"):
        data = result["data"]
        if data.get("access_token"):
            extra = None
            if provider.get("postExchange"):
                extra = await provider["postExchange"](data)
            return {"success": True, "tokens": provider["mapTokens"](data, extra)}
        else:
            error = data.get("error", "")
            if error in ("authorization_pending", "slow_down"):
                return {
                    "success": False,
                    "error": error,
                    "errorDescription": data.get("error_description") or data.get("message"),
                    "pending": error == "authorization_pending",
                }
            return {
                "success": False,
                "error": error or "no_access_token",
                "errorDescription": data.get("error_description") or data.get("message") or "No access token received",
            }

    data = result.get("data", {})
    return {
        "success": False,
        "error": data.get("error", "unknown"),
        "errorDescription": data.get("error_description"),
    }


async def refresh_access_token(provider_name: str, refresh_token: str) -> dict:
    """Refresh an access token using the provider's refresh endpoint."""
    provider = get_provider(provider_name)
    if not provider.get("refreshToken"):
        raise ValueError(f"Provider {provider_name} does not support token refresh")

    raw_tokens = await provider["refreshToken"](provider["config"], refresh_token)

    extra = None
    if provider.get("postExchange"):
        extra = await provider["postExchange"](raw_tokens)

    return provider["mapTokens"](raw_tokens, extra)
