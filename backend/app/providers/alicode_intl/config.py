"""Alibaba Intl provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class AlicodeIntlConfig(BaseModel):
    """Alibaba Intl provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Alibaba Intl"
    PROVIDER_ID: str = "alicode-intl"
    ALIAS: str = "alicode-intl"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://coding-intl.dashscope.aliyuncs.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class AlicodeIntlMetadata(BaseModel):
    """Alibaba Intl UI display metadata."""

    name: str = "Alibaba Intl"
    color: str = "#FF6A00"
    textIcon: str = "ALi"
