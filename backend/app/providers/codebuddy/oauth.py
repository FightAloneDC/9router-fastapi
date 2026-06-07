"""CodeBuddy OAuth handler — Polling flow."""

from __future__ import annotations

from typing import Optional

import httpx

from app.providers.oauth_base import DeviceCodeHandler


class CodebuddyOAuthHandler(DeviceCodeHandler):
    """OAuth handler for CodeBuddy (Tencent)."""

    PROVIDER_ID = "codebuddy"
    FLOW_TYPE = "polling"
    CONFIG = {
        "baseUrl": "https://copilot.tencent.com",
        "stateUrl": "https://copilot.tencent.com/v2/plugin/auth/state",
        "tokenUrl": "https://copilot.tencent.com/v2/plugin/auth/token",
        "refreshUrl": "https://copilot.tencent.com/v2/plugin/auth/token/refresh",
        "userAgent": "CLI/2.63.2 CodeBuddy/2.63.2",
        "platform": "CLI",
        "pollInterval": 5000,
    }

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                c["stateUrl"],
                headers={"User-Agent": c["userAgent"]},
            )
            if resp.status_code >= 400:
                raise Exception(f"CodeBuddy state request failed: {resp.text}")
            data = resp.json()
            return {
                "device_code": data.get("device_code") or data.get("code"),
                "user_code": data.get("user_code"),
                "verification_uri": c["baseUrl"],
                "expires_in": data.get("expires_in", 300),
                "interval": c.get("pollInterval", 5000) / 1000,
                "_requestId": data.get("request_id"),
            }

    async def poll_token(
        self, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None,
    ) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["tokenUrl"],
                headers={"Content-Type": "application/json", "User-Agent": c["userAgent"]},
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

    async def refresh_token(self, refresh_token: str) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["refreshUrl"],
                headers={"Content-Type": "application/json", "User-Agent": c["userAgent"]},
                json={"refresh_token": refresh_token},
            )
            if resp.status_code >= 400:
                raise Exception(f"CodeBuddy token refresh failed: {resp.text}")
            return resp.json()

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
        }
