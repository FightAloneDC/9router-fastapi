"""SiliconFlow provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class SiliconflowConfig(BaseModel):
    """SiliconFlow provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "SiliconFlow"
    PROVIDER_ID: str = "siliconflow"
    ALIAS: str = "sf"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.siliconflow.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding', 'image', 'tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class SiliconflowMetadata(BaseModel):
    """SiliconFlow UI display metadata."""

    name: str = "SiliconFlow"
    color: str = "#000000"
    textIcon: str = "SF"
