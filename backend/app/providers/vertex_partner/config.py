"""Vertex Partner provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class VertexPartnerConfig(BaseProviderConfig):
    """Vertex Partner provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Vertex Partner"
    PROVIDER_ID: str = "vertex-partner"
    ALIAS: str = "vxp"
    BASE_URL: str = "https://aiplatform.googleapis.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class VertexPartnerMetadata(BaseMetadata):
    """Vertex Partner UI display metadata."""

    name: str = "Vertex Partner"
    color: str = "#34A853"
    textIcon: str = "VP"
    icon: str = "Cloud"
    website: str = "https://cloud.google.com/vertex-ai"
