"""Cloudflare provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CloudflareAiConfig(BaseProviderConfig):
    """Cloudflare provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cloudflare"
    PROVIDER_ID: str = "cloudflare-ai"
    ALIAS: str = "cf"
    BASE_URL: str = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai"
    SERVICE_KINDS: list[str] = ["llm", "image"]
    CATEGORY: str = "freeTier"
    PROVIDER_SPECIFIC_DATA: bool = True


class CloudflareAiMetadata(BaseMetadata):
    """Cloudflare UI display metadata."""

    name: str = "Cloudflare"
    color: str = "#F38020"
    textIcon: str = "CF"
    icon: str = "Cloud"
    website: str = "https://developers.cloudflare.com/workers-ai/"
    notice: dict | None = {"text": "Workers AI free tier.", "apiKeyUrl": "https://dash.cloudflare.com/profile/api-tokens"}
