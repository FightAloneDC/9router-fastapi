"""Kimi Coding OAuth handler — Device Code flow."""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import settings
from app.providers.oauth_base import DeviceCodeHandler


class KimiCodingOAuthHandler(DeviceCodeHandler):
    """OAuth handler for Kimi Coding."""

    PROVIDER_ID = "kimi-coding"
    CONFIG = {
        "clientId": settings.KIMI_CODING_CLIENT_ID,
        "deviceCodeUrl": "https://auth.kimi.com/api/oauth/device_authorization",
        "tokenUrl": "https://auth.kimi.com/api/oauth/token",
    }

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["deviceCodeUrl"],
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                data={"client_id": c["clientId"]},
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
                },
            )
            try:
                data = resp.json()
            except Exception:
                data = {"error": "invalid_response", "error_description": resp.text}
            return {"ok": resp.status_code < 400, "data": data}

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
        }
