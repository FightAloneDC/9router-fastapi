"""NVIDIA NIM provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class NvidiaConfig(BaseModel):
    """NVIDIA NIM provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "NVIDIA NIM"
    PROVIDER_ID: str = "nvidia"
    ALIAS: str = "nvidia"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'tts', 'embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class NvidiaMetadata(BaseModel):
    """NVIDIA NIM UI display metadata."""

    name: str = "NVIDIA NIM"
    color: str = "#76B900"
    textIcon: str = "NV"
