"""Antigravity OAuth handler — Authorization Code (no PKCE, Google-based)."""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.providers import PROVIDER_ANTIGRAVITY
from app.providers.oauth_base import AuthCodeHandler

logger = logging.getLogger(__name__)


class AntigravityOAuthHandler(AuthCodeHandler):
    """OAuth handler for Antigravity (Google Cloud Code)."""

    PROVIDER_ID = PROVIDER_ANTIGRAVITY
    CONFIG = {
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

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str = "") -> str:
        c = self.config
        params = "&".join([
            f"client_id={c['clientId']}",
            "response_type=code",
            f"redirect_uri={redirect_uri}",
            f"scope={'%20'.join(c['scopes'])}",
            f"state={state}",
            "access_type=offline",
            "prompt=consent",
        ])
        return f"{c['authorizeUrl']}?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str = "", state: str = "",
    ) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["tokenUrl"],
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                data={
                    "grant_type": "authorization_code",
                    "client_id": c["clientId"],
                    "client_secret": c["clientSecret"],
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"Token exchange failed: {resp.text}")
            return resp.json()

    async def post_exchange(self, tokens: dict) -> dict:
        c = self.config
        load_headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
            "User-Agent": c["loadCodeAssistUserAgent"],
            "X-Goog-Api-Client": c["loadCodeAssistApiClient"],
            "Client-Metadata": c["loadCodeAssistClientMetadata"],
            "x-request-source": "local",
        }
        metadata = {"ideType": "IDE_UNSPECIFIED", "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            user_resp = await client.get(
                f"{c['userInfoUrl']}?alt=json",
                headers={"Authorization": f"Bearer {tokens['access_token']}", "x-request-source": "local"},
            )
            user_info = user_resp.json() if user_resp.status_code < 400 else {}

            project_id = ""
            tier_id = "legacy-tier"
            try:
                load_resp = await client.post(
                    c["loadCodeAssistEndpoint"],
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
                            c["onboardUserEndpoint"],
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

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
            "email": (extra or {}).get("userInfo", {}).get("email"),
            "projectId": (extra or {}).get("projectId"),
        }
