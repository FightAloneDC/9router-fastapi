"""GitHub OAuth handler — Device Code flow."""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import settings
from app.providers import PROVIDER_GITHUB
from app.providers.oauth_base import DeviceCodeHandler


class GithubOAuthHandler(DeviceCodeHandler):
    """OAuth handler for GitHub (Copilot)."""

    PROVIDER_ID = PROVIDER_GITHUB
    CONFIG = {
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

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["deviceCodeUrl"],
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                data={"client_id": c["clientId"], "scope": c["scopes"]},
            )
            if resp.status_code >= 400:
                raise Exception(f"Device code request failed: {resp.text}")
            return resp.json()

    async def poll_token(
        self, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None,
    ) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["tokenUrl"],
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                data={
                    "client_id": c["clientId"],
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            try:
                data = resp.json()
            except Exception:
                data = {"error": "invalid_response", "error_description": resp.text}
            return {"ok": resp.status_code < 400, "data": data}

    async def post_exchange(self, tokens: dict) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            copilot_resp = await client.get(
                c["copilotTokenUrl"],
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}",
                    "Accept": "application/json",
                    "X-GitHub-Api-Version": c["apiVersion"],
                    "User-Agent": c["userAgent"],
                },
            )
            copilot_token = copilot_resp.json() if copilot_resp.status_code < 400 else {}

            user_resp = await client.get(
                c["userInfoUrl"],
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}",
                    "Accept": "application/json",
                    "X-GitHub-Api-Version": c["apiVersion"],
                    "User-Agent": c["userAgent"],
                },
            )
            user_info = user_resp.json() if user_resp.status_code < 400 else {}

            return {"copilotToken": copilot_token, "userInfo": user_info}

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
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
