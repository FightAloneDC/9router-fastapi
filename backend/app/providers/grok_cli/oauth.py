"""Grok CLI OAuth handler — Device Code flow via auth.x.ai.

Faithful port of the Next.js reference at
``src/lib/oauth/providers/grok-cli.js``.

Device-code grant against auth.x.ai, then inference on
cli-chat-proxy.grok.com. Access tokens silently expire ~40-45 min after
login, so ``expiresAt`` is surfaced for the proactive refresh path.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.providers import PROVIDER_GROK_CLI
from app.providers.grok_cli.constants import (
    GROK_CLI_BASE_URL,
    GROK_CLI_CLIENT_ID,
    GROK_CLI_CLIENT_IDENTIFIER,
    GROK_CLI_DEVICE_CODE_URL,
    GROK_CLI_OAUTH_USER_AGENT,
    GROK_CLI_REFERRER,
    GROK_CLI_SCOPE,
    GROK_CLI_TOKEN_AUTH,
    GROK_CLI_TOKEN_URL,
    GROK_CLI_VERSION,
)
from app.providers.oauth_base import (
    DeviceCodeHandler,
    decode_jwt_payload,
    extract_email_from_token,
)

logger = logging.getLogger(__name__)


def _oauth_headers() -> dict[str, str]:
    """Headers used on auth.x.ai OAuth endpoints (official CLI value)."""
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": GROK_CLI_OAUTH_USER_AGENT,
    }


def _decode_id_token_email(id_token: str) -> Optional[str]:
    """Extract email from the xAI id_token JWT (unverified)."""
    payload = decode_jwt_payload(id_token)
    if not payload:
        return None
    return payload.get("email") or payload.get("preferred_username")


class GrokCliOAuthHandler(DeviceCodeHandler):
    """OAuth handler for Grok CLI (Grok Build)."""

    PROVIDER_ID = PROVIDER_GROK_CLI
    CONFIG = {
        "clientId": GROK_CLI_CLIENT_ID,
        "deviceCodeUrl": GROK_CLI_DEVICE_CODE_URL,
        "tokenUrl": GROK_CLI_TOKEN_URL,
        "refreshUrl": GROK_CLI_TOKEN_URL,
        "scope": GROK_CLI_SCOPE,
        "referrer": GROK_CLI_REFERRER,
    }

    async def request_device_code(
        self, code_challenge: str = "", options: Optional[dict] = None,
    ) -> dict:
        c = self.config
        form = {
            "client_id": c["clientId"],
            "scope": c["scope"],
        }
        # Official CLI sends referrer=grok-build
        if c.get("referrer"):
            form["referrer"] = c["referrer"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["deviceCodeUrl"], headers=_oauth_headers(), data=form,
            )
            if resp.status_code >= 400:
                raise Exception(
                    f"Grok CLI device code request failed: {resp.text}"
                )
            return resp.json()

    async def poll_token(
        self, device_code: str, code_verifier: str = "",
        extra_data: Optional[dict] = None,
    ) -> dict:
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["tokenUrl"],
                headers=_oauth_headers(),
                data={
                    "grant_type": (
                        "urn:ietf:params:oauth:grant-type:device_code"
                    ),
                    "device_code": device_code,
                    "client_id": c["clientId"],
                },
            )

        try:
            data = resp.json()
        except Exception:
            data = {
                "error": "invalid_response",
                "error_description": resp.text,
            }

        # Device flow: 400 + authorization_pending is expected while the
        # user is still approving in the browser.
        pending = data.get("error") in (
            "authorization_pending",
            "slow_down",
        )
        return {"ok": resp.is_success or pending, "data": data}

    async def post_exchange(self, tokens: dict) -> dict:
        """Best-effort user profile from cli-chat-proxy (non-fatal)."""
        access_token = tokens.get("access_token")
        if not access_token:
            return {"user": None}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{GROK_CLI_BASE_URL}/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                        "User-Agent": GROK_CLI_OAUTH_USER_AGENT,
                        "x-xai-token-auth": GROK_CLI_TOKEN_AUTH,
                        "x-grok-client-version": GROK_CLI_VERSION,
                        "x-grok-client-identifier": (
                            GROK_CLI_CLIENT_IDENTIFIER
                        ),
                    },
                )
            if resp.is_success:
                return {"user": resp.json()}
        except Exception:
            logger.debug("Grok CLI user profile fetch failed", exc_info=True)
        return {"user": None}

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh via auth.x.ai.

        Returns camelCase keys so the background token_refresh service
        can persist the new tokens.
        """
        c = self.config
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["refreshUrl"],
                headers=_oauth_headers(),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": c["clientId"],
                },
            )
            if resp.status_code >= 400:
                raise Exception(
                    f"Grok CLI token refresh failed: {resp.text}"
                )
            tokens = resp.json()

        email = (
            _decode_id_token_email(tokens.get("id_token", ""))
            or extract_email_from_token(tokens.get("access_token", ""))
        )
        psd: dict = {}
        if tokens.get("id_token"):
            psd["idToken"] = tokens["id_token"]
        if email:
            psd["email"] = email
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "providerSpecificData": psd,
        }

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        user = (extra or {}).get("user") or {}

        email = (
            _decode_id_token_email(tokens.get("id_token", ""))
            or extract_email_from_token(tokens.get("access_token", ""))
            or user.get("email")
        )
        user_id = user.get("userId") or user.get("principalId")
        display_name = " ".join(
            part for part in (
                user.get("firstName"), user.get("lastName"),
            ) if part
        ).strip() or None

        expires_in = tokens.get("expires_in")

        mapped = {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": expires_in,
            "scope": tokens.get("scope"),
            # Mirror identity into providerSpecificData so the handler can
            # set x-email / x-userid without depending on credential shape.
            "providerSpecificData": {
                "authMethod": "device_code",
                "idToken": tokens.get("id_token"),
                "email": email,
                "userId": user_id,
                "hasGrokCodeAccess": user.get("hasGrokCodeAccess"),
                "subscriptionTier": user.get("subscriptionTier"),
            },
        }
        if email:
            mapped["email"] = email
        if display_name:
            mapped["displayName"] = display_name
        return mapped
