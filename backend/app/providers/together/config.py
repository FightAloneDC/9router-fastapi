"""Together provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class TogetherConfig(BaseModel):
    """Together provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Together"
    PROVIDER_ID: str = "together"
    ALIAS: str = "tg"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.together.xyz/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class TogetherMetadata(BaseModel):
    """Together UI display metadata."""

    name: str = "Together"
    color: str = "#6C3AED"
    textIcon: str = "TG"
