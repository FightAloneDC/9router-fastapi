"""Kilocode OAuth handler — Device Code flow."""

from __future__ import annotations

from typing import Optional

import httpx

from app.providers.oauth_base import DeviceCodeHandler


class KilocodeOAuthHandler(DeviceCodeHandler):
    """OAuth handler for Kilocode."""

    PROVIDER_ID = "kilocode"
    CONFIG = {
        "apiBaseUrl": "https://api.kilo.ai",
        "initiateUrl": "https://api.kilo.ai/api/device-auth/codes",
        "pollUrlBase": "https://api.kilo.ai/api/device-auth/codes",
    }

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["initiateUrl"],
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

    async def poll_token(
        self, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None,
    ) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{c['pollUrlBase']}/{device_code}")
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
                        f"{c['apiBaseUrl']}/api/profile",
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

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        result = {
            "accessToken": tokens.get("access_token"),
            "refreshToken": None,
            "expiresIn": None,
            "email": tokens.get("_userEmail"),
        }
        if tokens.get("_orgId"):
            result["providerSpecificData"] = {"orgId": tokens["_orgId"]}
        return result
