"""Qoder provider definition.

Static provider characteristics — runtime data (OAuth tokens, PAT tokens)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class QoderConfig(BaseProviderConfig):
    """Qoder provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Qoder"
    PROVIDER_ID: str = "qoder"
    ALIAS: str = "qd"
    BASE_URL: str = "https://api3.qoder.sh"
    SERVICE_KINDS: list[str] = ["llm"]

    # ── Connection defaults ─────────────────────────────────────────────
    FORMAT: str = "qoder"  # Custom format — not OpenAI-compatible
    VALIDATION_TYPE: str = "qoder"


class QoderMetadata(BaseMetadata):
    """Qoder UI display metadata."""

    name: str = "Qoder"
    color: str = "#6366F1"
    textIcon: str = "QD"
