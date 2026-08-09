"""Keelcode OAuth handler — Device Code flow."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.providers import PROVIDER_KEELCODE
from app.providers.keelcode.constants import (
    CLIENT_ID,
    DEFAULT_POLL_INTERVAL,
    DEVICE_CODE_URL,
    DEVICE_GRANT_TYPE,
    DEVICE_TOKEN_URL,
)
from app.providers.oauth_base import DeviceCodeHandler


class KeelcodeOAuthHandler(DeviceCodeHandler):
    """OAuth handler for Keelcode device approval."""

    PROVIDER_ID = PROVIDER_KEELCODE
    CONFIG: dict[str, Any] = {
        "clientId": CLIENT_ID,
        "deviceCodeUrl": DEVICE_CODE_URL,
        "tokenUrl": DEVICE_TOKEN_URL,
    }

    async def request_device_code(
        self,
        code_challenge: str = "",
        options: Optional[dict] = None,
    ) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["deviceCodeUrl"],
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={"client_id": c["clientId"]},
            )
            if resp.status_code >= 400:
                raise Exception(
                    f"Device code request failed: {resp.text}"
                )
            data = resp.json()
            return {
                "device_code": data.get("device_code"),
                "user_code": data.get("user_code"),
                "verification_uri": data.get(
                    "verification_uri",
                    "https://keelcode.ai/device",
                ),
                "verification_uri_complete": data.get(
                    "verification_uri_complete"
                ),
                "expires_in": data.get("expires_in", 600),
                "interval": data.get(
                    "interval", DEFAULT_POLL_INTERVAL
                ),
            }

    async def poll_token(
        self,
        device_code: str,
        code_verifier: str = "",
        extra_data: Optional[dict] = None,
    ) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["tokenUrl"],
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "grant_type": DEVICE_GRANT_TYPE,
                    "client_id": c["clientId"],
                    "device_code": device_code,
                },
            )
            try:
                data = resp.json()
            except Exception:
                data = {
                    "error": "invalid_response",
                    "error_description": resp.text,
                }
            # Pending/slow_down arrive as HTTP 400 with
            # standard OAuth device-code error codes.
            if resp.status_code < 400 and data.get(
                "access_token"
            ):
                return {"ok": True, "data": data}
            return {"ok": False, "data": data}

    def map_tokens(
        self,
        tokens: dict,
        extra: Optional[dict] = None,
    ) -> dict:
        result: dict[str, Any] = {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
            "email": tokens.get("email")
            or (extra or {}).get("email"),
        }
        return result
