"""Amazon Bedrock provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class AmazonBedrockConfig(BaseModel):
    """Amazon Bedrock provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Amazon Bedrock"
    PROVIDER_ID: str = "amazon-bedrock"
    ALIAS: str = "bedrock"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://bedrock-runtime.{region}.amazonaws.com"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class AmazonBedrockMetadata(BaseModel):
    """Amazon Bedrock UI display metadata."""

    name: str = "Amazon Bedrock"
    color: str = "#FF9900"
    textIcon: str = "AB"
