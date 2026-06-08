"""AskCodi provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AskcodiConfig(BaseProviderConfig):
    """AskCodi provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "AskCodi"
    PROVIDER_ID: str = "askcodi"
    ALIAS: str = "ac"
    BASE_URL: str = "https://api.askcodi.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class AskcodiMetadata(BaseMetadata):
    """AskCodi UI display metadata."""

    name: str = "AskCodi"
    color: str = "#6366F1"
    textIcon: str = "AC"
    icon: str = "Code"
    website: str = "https://www.askcodi.com/"
    notice: dict | None = {"text": "Free tier: 100K token free credit on signup.", "apiKeyUrl": "https://www.askcodi.com/api_keys"}
