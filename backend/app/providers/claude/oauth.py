"""Claude OAuth handler — Authorization Code + PKCE."""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import settings
from app.providers import PROVIDER_CLAUDE
from app.providers.oauth_base import AuthCodePKCEHandler


class ClaudeOAuthHandler(AuthCodePKCEHandler):
    """OAuth handler for Claude (Anthropic)."""

    PROVIDER_ID = PROVIDER_CLAUDE
    CONFIG = {
        "clientId": settings.CLAUDE_CLIENT_ID,
        "authorizeUrl": "https://claude.ai/oauth/authorize",
        "tokenUrl": "https://api.anthropic.com/v1/oauth/token",
        "scopes": ["org:create_api_key", "user:profile", "user:inference"],
        "codeChallengeMethod": "S256",
    }

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str = "") -> str:
        c = self.config
        params = "&".join([
            "code=true",
            f"client_id={c['clientId']}",
            "response_type=code",
            f"redirect_uri={redirect_uri}",
            f"scope={'%20'.join(c['scopes'])}",
            f"code_challenge={code_challenge}",
            f"code_challenge_method={c['codeChallengeMethod']}",
            f"state={state}",
        ])
        return f"{c['authorizeUrl']}?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str = "", state: str = "",
    ) -> dict:
        auth_code = code
        code_state = ""
        if "#" in auth_code:
            parts = auth_code.split("#")
            auth_code = parts[0]
            code_state = parts[1] if len(parts) > 1 else ""

        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["tokenUrl"],
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "code": auth_code,
                    "state": code_state or state,
                    "grant_type": "authorization_code",
                    "client_id": c["clientId"],
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"Token exchange failed: {resp.text}")
            return resp.json()

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
        }
