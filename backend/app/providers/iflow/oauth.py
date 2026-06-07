"""iFlow OAuth handler — Authorization Code (no PKCE, Basic auth)."""

from __future__ import annotations

import base64
from typing import Optional

import httpx

from app.config import settings
from app.providers.oauth_base import AuthCodeHandler


class IflowOAuthHandler(AuthCodeHandler):
    """OAuth handler for iFlow."""

    PROVIDER_ID = "iflow"
    CONFIG = {
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

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str = "") -> str:
        c = self.config
        params = "&".join([
            f"loginMethod={c['extraParams']['loginMethod']}",
            f"type={c['extraParams']['type']}",
            f"redirect={redirect_uri}",
            f"state={state}",
            f"client_id={c['clientId']}",
        ])
        return f"{c['authorizeUrl']}?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str = "", state: str = "",
    ) -> dict:
        c = self.config
        basic_auth = base64.b64encode(f"{c['clientId']}:{c['clientSecret']}".encode()).decode()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["tokenUrl"],
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "Authorization": f"Basic {basic_auth}",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": c["clientId"],
                    "client_secret": c["clientSecret"],
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"Token exchange failed: {resp.text}")
            return resp.json()

    async def post_exchange(self, tokens: dict) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{c['userInfoUrl']}?accessToken={tokens['access_token']}",
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

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        user_info = (extra or {}).get("userInfo", {})
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "apiKey": user_info.get("apiKey"),
            "email": user_info.get("email") or user_info.get("phone"),
            "displayName": user_info.get("nickname") or user_info.get("name"),
        }
