"""Edge TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class EdgeTTSConfig(BaseModel):
    """Edge TTS provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Edge TTS"
    PROVIDER_ID: str = "edge-tts"
    ALIAS: str = "edge"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://speech.platform.bing.com"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class EdgeTTSMetadata(BaseModel):
    """Edge TTS UI display metadata."""

    name: str = "Edge TTS"
    color: str = "#0078D4"
    textIcon: str = "ET"
