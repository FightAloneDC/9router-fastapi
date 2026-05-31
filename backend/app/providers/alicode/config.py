"""Alibaba provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class AlicodeConfig(BaseModel):
    """Alibaba provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Alibaba"
    PROVIDER_ID: str = "alicode"
    ALIAS: str = "alicode"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://coding.dashscope.aliyuncs.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class AlicodeMetadata(BaseModel):
    """Alibaba UI display metadata."""

    name: str = "Alibaba"
    color: str = "#FF6A00"
    textIcon: str = "ALi"
