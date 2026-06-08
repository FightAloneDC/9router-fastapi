"""Amazon Bedrock provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AmazonBedrockConfig(BaseProviderConfig):
    """Amazon Bedrock provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Amazon Bedrock"
    PROVIDER_ID: str = "amazon-bedrock"
    ALIAS: str = "bedrock"
    BASE_URL: str = "https://bedrock-runtime.{region}.amazonaws.com"
    SERVICE_KINDS: list[str] = ["llm"]
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""


class AmazonBedrockMetadata(BaseMetadata):
    """Amazon Bedrock UI display metadata."""

    name: str = "Amazon Bedrock"
    color: str = "#FF9900"
    textIcon: str = "AB"
    icon: str = "Cloud"
    website: str = "https://aws.amazon.com/bedrock/"
