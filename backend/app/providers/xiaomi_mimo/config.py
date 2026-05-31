"""Xiaomi MiMo provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class XiaomiMimoConfig(BaseModel):
    """Xiaomi MiMo provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Xiaomi MiMo"
    PROVIDER_ID: str = "xiaomi-mimo"
    ALIAS: str = "mimo"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.xiaomimimo.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class XiaomiMimoMetadata(BaseModel):
    """Xiaomi MiMo UI display metadata."""

    name: str = "Xiaomi MiMo"
    color: str = "#FF6900"
    textIcon: str = "XM"
