"""Base OAuth handler classes.

Provides base classes for different OAuth flows:
- AuthCodeHandler: Authorization Code (+ optional PKCE)
- DeviceCodeHandler: Device Code flow
- ImportTokenHandler: Import token directly (no OAuth flow)
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


# ── Shared Utilities ─────────────────────────────────────────────────────────


def decode_jwt_payload(jwt: str) -> Optional[dict]:
    """Decode JWT access token payload without verification."""
    try:
        if not jwt or not isinstance(jwt, str):
            return None
        parts = jwt.split(".")
        if len(parts) != 3:
            return None
        base64_str = parts[1].replace("-", "+").replace("_", "/")
        padding = (4 - len(base64_str) % 4) % 4
        base64_str += "=" * padding
        return json.loads(base64.b64decode(base64_str).decode("utf-8"))
    except Exception:
        return None


def extract_email_from_token(access_token: str) -> Optional[str]:
    """Extract email from JWT access token."""
    payload = decode_jwt_payload(access_token)
    if not payload:
        return None
    return payload.get("email") or payload.get("preferred_username") or payload.get("sub")


# ── Base Handler ─────────────────────────────────────────────────────────────


class BaseOAuthHandler:
    """Base class for all OAuth provider handlers."""

    # Override in subclass
    PROVIDER_ID: str = ""
    FLOW_TYPE: str = ""  # "authorization_code_pkce", "authorization_code", "device_code", "polling", "import_token"
    CONFIG: dict[str, Any] = {}

    @property
    def config(self) -> dict[str, Any]:
        return self.CONFIG

    @property
    def flow_type(self) -> str:
        return self.FLOW_TYPE

    def get_config(self) -> dict[str, Any]:
        """Return provider OAuth config."""
        return self.config

    def build_auth_url(self, redirect_uri: str, state: str, code_challenge: str = "") -> str:
        """Build authorization URL. Override in subclass."""
        raise NotImplementedError(f"{self.PROVIDER_ID} does not support auth URL building")

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str = "", state: str = "",
    ) -> dict:
        """Exchange authorization code for tokens. Override in subclass."""
        raise NotImplementedError(f"{self.PROVIDER_ID} does not support code exchange")

    async def post_exchange(self, tokens: dict) -> dict:
        """Post-exchange hook (e.g. fetch user info). Override if needed."""
        return {}

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        """Map provider tokens to standard format. Override in subclass."""
        raise NotImplementedError(f"{self.PROVIDER_ID} does not support token mapping")

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        """Request device code. Override for device_code flow."""
        raise NotImplementedError(f"{self.PROVIDER_ID} does not support device code flow")

    async def poll_token(
        self, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None,
    ) -> dict:
        """Poll for token. Override for device_code flow.

        Returns: {"ok": bool, "data": dict}
        """
        raise NotImplementedError(f"{self.PROVIDER_ID} does not support token polling")

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token. Override if provider supports refresh."""
        raise NotImplementedError(f"{self.PROVIDER_ID} does not support token refresh")


# ── Auth Code Handler ────────────────────────────────────────────────────────


class AuthCodeHandler(BaseOAuthHandler):
    """Base handler for Authorization Code flow (with optional PKCE).

    Subclasses must override:
    - CONFIG, FLOW_TYPE, PROVIDER_ID
    - build_auth_url()
    - exchange_code()
    - map_tokens()
    """

    FLOW_TYPE = "authorization_code"


class AuthCodePKCEHandler(AuthCodeHandler):
    """Base handler for Authorization Code + PKCE flow."""

    FLOW_TYPE = "authorization_code_pkce"


# ── Device Code Handler ──────────────────────────────────────────────────────


class DeviceCodeHandler(BaseOAuthHandler):
    """Base handler for Device Code flow.

    Subclasses must override:
    - CONFIG, PROVIDER_ID
    - request_device_code()
    - poll_token()
    - map_tokens()
    """

    FLOW_TYPE = "device_code"


# ── Import Token Handler ─────────────────────────────────────────────────────


class ImportTokenHandler(BaseOAuthHandler):
    """Base handler for import-token flow (no OAuth redirect).

    Subclasses must override:
    - CONFIG, PROVIDER_ID
    - map_tokens()
    """

    FLOW_TYPE = "import_token"
