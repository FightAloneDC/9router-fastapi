"""DeepSeek provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class DeepseekConfig(BaseModel):
    """DeepSeek provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "DeepSeek"
    PROVIDER_ID: str = "deepseek"
    ALIAS: str = "ds"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.deepseek.com"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class DeepseekMetadata(BaseModel):
    """DeepSeek UI display metadata."""

    name: str = "DeepSeek"
    color: str = "#0066FF"
    textIcon: str = "DS"
