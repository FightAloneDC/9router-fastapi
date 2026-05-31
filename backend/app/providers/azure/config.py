"""Azure OpenAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class AzureConfig(BaseModel):
    """Azure OpenAI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Azure OpenAI"
    PROVIDER_ID: str = "azure"
    ALIAS: str = "az"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://{resource}.openai.azure.com/openai"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "api-key"
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class AzureMetadata(BaseModel):
    """Azure OpenAI UI display metadata."""

    name: str = "Azure OpenAI"
    color: str = "#0078D4"
    textIcon: str = "AZ"
