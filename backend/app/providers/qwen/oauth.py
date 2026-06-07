"""Qwen OAuth handler — Device Code flow."""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import settings
from app.providers.oauth_base import DeviceCodeHandler


class QwenOAuthHandler(DeviceCodeHandler):
    """OAuth handler for Qwen."""

    PROVIDER_ID = "qwen"
    CONFIG = {
        "clientId": settings.QWEN_CLIENT_ID,
        "deviceCodeUrl": "https://chat.qwen.ai/api/v1/oauth2/device/code",
        "tokenUrl": "https://chat.qwen.ai/api/v1/oauth2/token",
        "scope": "openid profile email model.completion",
        "codeChallengeMethod": "S256",
    }

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["deviceCodeUrl"],
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                data={
                    "client_id": c["clientId"],
                    "scope": c["scope"],
                    "code_challenge": code_challenge,
                    "code_challenge_method": c["codeChallengeMethod"],
                },
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
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": c["clientId"],
                    "device_code": device_code,
                    "code_verifier": code_verifier,
                },
            )
            return {"ok": resp.status_code < 400, "data": resp.json()}

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "providerSpecificData": {"resourceUrl": tokens.get("resource_url")},
        }
