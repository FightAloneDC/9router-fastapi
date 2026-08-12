"""Qoder OAuth handler — Device Token flow (custom).

⚠️  CRITICAL: Do NOT modify this provider without user approval.
    Extensive investigation and trial-error has been done.
    See docs/qoder/BUG-FIXING-LOG.md before making any changes.
"""

from __future__ import annotations

from typing import Optional

import httpx
from pydantic import BaseModel

from app.providers import PROVIDER_QODER
from app.providers.oauth_base import DeviceCodeHandler
from app.services.outbound_proxy import create_upstream_client


class QoderPATRequest(BaseModel):
    personalToken: str


class QoderOAuthHandler(DeviceCodeHandler):
    """OAuth handler for Qoder (custom device token flow)."""

    PROVIDER_ID = PROVIDER_QODER
    CONFIG = {
        "openApiBaseUrl": "https://openapi.qoder.sh",
        "centerBaseUrl": "https://center.qoder.sh",
        "chatBaseUrl": "https://api3.qoder.sh",
        "deviceTokenUrl": "https://openapi.qoder.sh/api/v1/deviceToken/poll",
        "refreshUrl": "https://openapi.qoder.sh/api/v1/jobToken/refresh",
        "userInfoUrl": "https://openapi.qoder.sh/api/v1/userinfo",
        "quotaUsageUrl": "https://openapi.qoder.sh/api/v2/quota/usage",
        "loginUrl": "https://qoder.com/device/selectAccounts",
    }

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        from app.providers.qoder.auth import initiate_device_flow

        flow = initiate_device_flow()
        return {
            "device_code": flow["nonce"],
            "user_code": flow["nonce"][:8].upper(),
            "verification_uri": self.config["loginUrl"],
            "verification_uri_complete": flow["verification_uri_complete"],
            "expires_in": 300,
            "interval": 2,
            "codeVerifier": flow["code_verifier"],
            "_qoderNonce": flow["nonce"],
            "_qoderMachineId": flow["machine_id"],
        }

    async def poll_token(
        self, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None,
    ) -> dict:
        from app.providers.qoder.auth import poll_device_token

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
                    "_qoderMachineId": (extra_data or {}).get("_qoderMachineId"),
                },
            }

        return {"ok": False, "data": {"error": "authorization_pending"}}

    async def post_exchange(self, tokens: dict) -> dict:
        from app.providers.qoder.auth import fetch_user_info

        access_token = tokens.get("access_token")
        if not access_token:
            return {}
        try:
            user_info = await fetch_user_info(access_token)
            return {"userInfo": user_info}
        except Exception:
            return {}

    async def refresh_token(self, refresh_token: str) -> dict:
        c = self.config
        async with create_upstream_client(timeout=30.0) as client:
            resp = await client.post(
                c["refreshUrl"],
                headers={"Content-Type": "application/json"},
                json={"refresh_token": refresh_token},
            )
            if resp.status_code >= 400:
                raise Exception(f"Qoder token refresh failed: {resp.text}")
            return resp.json()

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        psd = {}
        user_info = (extra or {}).get("userInfo", {})

        user_id = tokens.get("user_id") or user_info.get("id")
        if user_id:
            psd["userId"] = user_id

        if tokens.get("_qoderMachineId"):
            psd["machineId"] = tokens["_qoderMachineId"]

        email = tokens.get("email") or user_info.get("email")
        display_name = (
            tokens.get("display_name")
            or user_info.get("name")
            or user_info.get("displayName")
        )

        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "email": email,
            "displayName": display_name,
            "providerSpecificData": psd if psd else None,
        }
