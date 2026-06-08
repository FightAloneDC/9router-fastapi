"""Vertex AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class VertexConfig(BaseProviderConfig):
    """Vertex AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Vertex AI"
    PROVIDER_ID: str = "vertex"
    ALIAS: str = "vx"
    BASE_URL: str = "https://aiplatform.googleapis.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class VertexMetadata(BaseMetadata):
    """Vertex AI UI display metadata."""

    name: str = "Vertex AI"
    color: str = "#4285F4"
    textIcon: str = "VX"
    icon: str = "Cloud"
    website: str = "https://cloud.google.com/vertex-ai"
    notice: dict | None = {"text": "New Google Cloud accounts get $300 free credits.", "apiKeyUrl": "https://console.cloud.google.com/iam-admin/serviceaccounts"}
