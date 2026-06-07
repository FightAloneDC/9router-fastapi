"""Gemini CLI OAuth handler — Authorization Code (no PKCE)."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.providers.oauth_base import AuthCodeHandler

logger = logging.getLogger(__name__)


class GeminiOAuthHandler(AuthCodeHandler):
    """OAuth handler for Gemini CLI (Google)."""

    PROVIDER_ID = "gemini-cli"
    CONFIG = {
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            user_resp = await client.get(
                f"{c['userInfoUrl']}?alt=json",
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

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
            "email": (extra or {}).get("userInfo", {}).get("email"),
            "projectId": (extra or {}).get("projectId"),
        }
