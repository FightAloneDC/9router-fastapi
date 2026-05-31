"""OpenCode Go provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class OpenCodeGoConfig(BaseModel):
    """OpenCode Go provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenCode Go"
    PROVIDER_ID: str = "opencode-go"
    ALIAS: str = "ocg"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://opencode.ai/api/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class OpenCodeGoMetadata(BaseModel):
    """OpenCode Go UI display metadata."""

    name: str = "OpenCode Go"
    color: str = "#E87040"
    textIcon: str = "OC"
