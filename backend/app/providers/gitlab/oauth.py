"""GitLab OAuth handler — Authorization Code + PKCE."""

from __future__ import annotations

from typing import Optional

import httpx

from app.providers.oauth_base import AuthCodePKCEHandler


class GitlabOAuthHandler(AuthCodePKCEHandler):
    """OAuth handler for GitLab."""

    PROVIDER_ID = "gitlab"
    CONFIG = {
        "defaultBaseUrl": "https://gitlab.com",
        "authorizeUrlPath": "/oauth/authorize",
        "tokenUrlPath": "/oauth/token",
        "userInfoUrlPath": "/api/v4/user",
        "scope": "api read_user",
        "codeChallengeMethod": "S256",
    }

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str = "") -> str:
        c = self.config
        base_url = c.get("defaultBaseUrl", "https://gitlab.com")
        params = "&".join([
            "response_type=code",
            f"client_id={c.get('clientId', '')}",
            f"redirect_uri={redirect_uri}",
            f"scope={c['scope'].replace(' ', '%20')}",
            f"state={state}",
            f"code_challenge={code_challenge}",
            f"code_challenge_method={c['codeChallengeMethod']}",
        ])
        return f"{base_url}{c['authorizeUrlPath']}?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str = "", state: str = "",
    ) -> dict:
        c = self.config
        base_url = c.get("defaultBaseUrl", "https://gitlab.com")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}{c['tokenUrlPath']}",
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"GitLab token exchange failed: {resp.text}")
            return resp.json()

    async def post_exchange(self, tokens: dict) -> dict:
        c = self.config
        base_url = c.get("defaultBaseUrl", "https://gitlab.com")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{base_url}{c['userInfoUrlPath']}",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            user_info = resp.json() if resp.status_code < 400 else {}
            return {"userInfo": user_info}

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
            "email": (extra or {}).get("userInfo", {}).get("email"),
            "displayName": (extra or {}).get("userInfo", {}).get("name"),
        }
