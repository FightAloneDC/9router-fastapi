"""Kimi provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class KimiConfig(BaseModel):
    """Kimi provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Kimi"
    PROVIDER_ID: str = "kimi"
    ALIAS: str = "kimi"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.moonshot.cn/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class KimiMetadata(BaseModel):
    """Kimi UI display metadata."""

    name: str = "Kimi"
    color: str = "#1E3A8A"
    textIcon: str = "KM"
