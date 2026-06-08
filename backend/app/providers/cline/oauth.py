"""Cline OAuth handler — Authorization Code (special base64-encoded token callback)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.providers import PROVIDER_CLINE
from app.providers.oauth_base import AuthCodeHandler


class ClineOAuthHandler(AuthCodeHandler):
    """OAuth handler for Cline.

    Cline encodes token data as base64 in the callback code parameter.
    Falls back to token exchange endpoint if base64 decode fails.
    """

    PROVIDER_ID = PROVIDER_CLINE
    CONFIG = {
        "appBaseUrl": "https://app.cline.bot",
        "apiBaseUrl": "https://api.cline.bot",
        "authorizeUrl": "https://api.cline.bot/api/v1/auth/authorize",
        "tokenExchangeUrl": "https://api.cline.bot/api/v1/auth/token",
        "refreshUrl": "https://api.cline.bot/api/v1/auth/refresh",
    }

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str = "") -> str:
        c = self.config
        params = "&".join([
            "client_type=extension",
            f"callback_url={redirect_uri}",
            f"redirect_uri={redirect_uri}",
        ])
        return f"{c['authorizeUrl']}?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str = "", state: str = "",
    ) -> dict:
        c = self.config
        try:
            base64_str = code
            padding = (4 - len(base64_str) % 4) % 4
            if padding != 4:
                base64_str += "=" * padding
            decoded = base64.b64decode(base64_str).decode("utf-8")
            last_brace = decoded.rfind("}")
            if last_brace == -1:
                raise Exception("No JSON found in decoded code")
            token_data = json.loads(decoded[: last_brace + 1])
            return {
                "access_token": token_data.get("accessToken"),
                "refresh_token": token_data.get("refreshToken"),
                "email": token_data.get("email"),
                "firstName": token_data.get("firstName"),
                "lastName": token_data.get("lastName"),
                "expires_at": token_data.get("expiresAt"),
            }
        except Exception:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    c["tokenExchangeUrl"],
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    json={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_type": "extension",
                        "redirect_uri": redirect_uri,
                    },
                )
                if resp.status_code >= 400:
                    raise Exception(f"Cline token exchange failed: {resp.text}")
                data = resp.json()
                inner = data.get("data", data)
                return {
                    "access_token": inner.get("accessToken"),
                    "refresh_token": inner.get("refreshToken"),
                    "email": inner.get("userInfo", {}).get("email", ""),
                    "expires_at": inner.get("expiresAt"),
                }

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        expires_in = None
        if tokens.get("expires_at"):
            try:
                exp = datetime.fromisoformat(tokens["expires_at"].replace("Z", "+00:00"))
                expires_in = int((exp - datetime.now(timezone.utc)).total_seconds())
            except Exception:
                expires_in = 3600
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": expires_in or 3600,
            "email": tokens.get("email"),
            "providerSpecificData": {
                "firstName": tokens.get("firstName"),
                "lastName": tokens.get("lastName"),
            },
        }
