"""Volcengine Ark provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class VolcengineArkConfig(BaseModel):
    """Volcengine Ark provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Volcengine Ark"
    PROVIDER_ID: str = "volcengine-ark"
    ALIAS: str = "ark"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class VolcengineArkMetadata(BaseModel):
    """Volcengine Ark UI display metadata."""

    name: str = "Volcengine Ark"
    color: str = "#1677FF"
    textIcon: str = "ARK"
