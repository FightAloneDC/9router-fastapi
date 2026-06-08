"""OpenAI OAuth handler — Authorization Code + PKCE."""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import settings
from app.providers import PROVIDER_OPENAI
from app.providers.codex.oauth import CodexOAuthHandler


class OpenaiOAuthHandler(CodexOAuthHandler):
    """OAuth handler for OpenAI (same flow as Codex, different originator)."""

    PROVIDER_ID = PROVIDER_OPENAI
    CONFIG = {
        "clientId": settings.CODEX_CLIENT_ID,
        "authorizeUrl": "https://auth.openai.com/oauth/authorize",
        "tokenUrl": "https://auth.openai.com/oauth/token",
        "scope": "openid profile email offline_access",
        "codeChallengeMethod": "S256",
        "extraParams": {
            "id_token_add_organizations": "true",
            "originator": "openai_native",
        },
    }
