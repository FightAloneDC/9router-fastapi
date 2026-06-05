"""AssemblyAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AssemblyaiConfig(BaseProviderConfig):
    """AssemblyAI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "AssemblyAI"
    PROVIDER_ID: str = "assemblyai"
    ALIAS: str = "aai"
    BASE_URL: str = "https://api.assemblyai.com/v1"
    SERVICE_KINDS: list[str] = ["stt"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = ""


class AssemblyaiMetadata(BaseMetadata):
    """AssemblyAI UI display metadata."""

    name: str = "AssemblyAI"
    color: str = "#0F172A"
    textIcon: str = "AA"
