"""Vercel AI Gateway provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class VercelAiGatewayConfig(BaseProviderConfig):
    """Vercel AI Gateway provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Vercel AI Gateway"
    PROVIDER_ID: str = "vercel-ai-gateway"
    ALIAS: str = "vag"
    BASE_URL: str = "https://ai-gateway.vercel.sh/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class VercelAiGatewayMetadata(BaseMetadata):
    """Vercel AI Gateway UI display metadata."""

    name: str = "Vercel AI Gateway"
    color: str = "#000000"
    textIcon: str = "VA"
