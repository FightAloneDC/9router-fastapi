"""Command Code provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class CommandCodeConfig(BaseModel):
    """Command Code provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Command Code"
    PROVIDER_ID: str = "commandcode"
    ALIAS: str = "cmc"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.commandcode.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class CommandCodeMetadata(BaseModel):
    """Command Code UI display metadata."""

    name: str = "Command Code"
    color: str = "#000000"
    textIcon: str = "CC"
