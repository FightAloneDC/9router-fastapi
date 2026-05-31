"""AssemblyAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class AssemblyAIConfig(BaseModel):
    """AssemblyAI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "AssemblyAI"
    PROVIDER_ID: str = "assemblyai"
    ALIAS: str = "aai"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.assemblyai.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['stt']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class AssemblyAIMetadata(BaseModel):
    """AssemblyAI UI display metadata."""

    name: str = "AssemblyAI"
    color: str = "#0F172A"
    textIcon: str = "AA"
