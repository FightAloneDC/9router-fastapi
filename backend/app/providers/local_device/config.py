"""Local Device provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class LocalDeviceConfig(BaseModel):
    """Local Device provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Local Device"
    PROVIDER_ID: str = "local-device"
    ALIAS: str = "local"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "http://localhost"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class LocalDeviceMetadata(BaseModel):
    """Local Device UI display metadata."""

    name: str = "Local Device"
    color: str = "#6B7280"
    textIcon: str = "LD"
