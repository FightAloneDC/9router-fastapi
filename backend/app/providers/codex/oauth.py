"""Codex OAuth handler — Authorization Code + PKCE."""

from __future__ import annotations

import json
import base64
from typing import Optional

import httpx

from app.config import settings
from app.providers import PROVIDER_CODEX
from app.providers.oauth_base import AuthCodePKCEHandler, decode_jwt_payload


def _extract_codex_account_info(id_token: str) -> dict:
    payload = decode_jwt_payload(id_token)
    if not payload:
        return {}
    chatgpt = payload.get("https://api.openai.com/auth", {})
    return {
        "email": payload.get("email"),
        "chatgptAccountId": chatgpt.get("chatgpt_account_id"),
        "chatgptPlanType": chatgpt.get("chatgpt_plan_type"),
    }


class CodexOAuthHandler(AuthCodePKCEHandler):
    """OAuth handler for Codex (OpenAI)."""

    PROVIDER_ID = PROVIDER_CODEX
    CONFIG = {
        "clientId": settings.CODEX_CLIENT_ID,
        "authorizeUrl": "https://auth.openai.com/oauth/authorize",
        "tokenUrl": "https://auth.openai.com/oauth/token",
        "scope": "openid profile email offline_access",
        "codeChallengeMethod": "S256",
        "extraParams": {
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "codex_cli_rs",
        },
    }

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str = "") -> str:
        c = self.config
        params = {
            "response_type": "code",
            "client_id": c["clientId"],
            "redirect_uri": redirect_uri,
            "scope": c["scope"],
            "code_challenge": code_challenge,
            "code_challenge_method": c["codeChallengeMethod"],
            **c["extraParams"],
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{c['authorizeUrl']}?{query}"

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
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"Token exchange failed: {resp.text}")
            return resp.json()

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        info = _extract_codex_account_info(tokens.get("id_token", ""))
        mapped = {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
        }
        if info.get("email"):
            mapped["email"] = info["email"]
        if info.get("chatgptAccountId") or info.get("chatgptPlanType"):
            mapped["providerSpecificData"] = {
                "chatgptAccountId": info.get("chatgptAccountId"),
                "chatgptPlanType": info.get("chatgptPlanType"),
            }
        return mapped
