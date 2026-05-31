"""Cloudflare provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class CloudflareAIConfig(BaseModel):
    """Cloudflare provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cloudflare"
    PROVIDER_ID: str = "cloudflare-ai"
    ALIAS: str = "cf"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class CloudflareAIMetadata(BaseModel):
    """Cloudflare UI display metadata."""

    name: str = "Cloudflare"
    color: str = "#F38020"
    textIcon: str = "CF"
