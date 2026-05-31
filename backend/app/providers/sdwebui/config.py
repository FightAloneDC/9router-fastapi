"""Stable Diffusion WebUI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class SDWebUIConfig(BaseModel):
    """Stable Diffusion WebUI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Stable Diffusion WebUI"
    PROVIDER_ID: str = "sdwebui"
    ALIAS: str = "sd"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "http://localhost:7860"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class SDWebUIMetadata(BaseModel):
    """Stable Diffusion WebUI UI display metadata."""

    name: str = "Stable Diffusion WebUI"
    color: str = "#A855F7"
    textIcon: str = "SD"
