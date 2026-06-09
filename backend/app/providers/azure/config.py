"""Azure OpenAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AzureConfig(BaseProviderConfig):
    """Azure OpenAI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Azure OpenAI"
    PROVIDER_ID: str = "azure"
    ALIAS: str = "az"
    BASE_URL: str = "https://{resource}.openai.azure.com/openai"
    SERVICE_KINDS: list[str] = ["llm"]
    AUTH_HEADER: str = "api-key"
    AUTH_PREFIX: str = ""
    PROVIDER_SPECIFIC_DATA: bool = True


class AzureMetadata(BaseMetadata):
    """Azure OpenAI UI display metadata."""

    name: str = "Azure OpenAI"
    color: str = "#0078D4"
    textIcon: str = "AZ"
    icon: str = "Cloud"
    website: str = "https://azure.microsoft.com"
