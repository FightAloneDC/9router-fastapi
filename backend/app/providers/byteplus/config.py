"""BytePlus ModelArk provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class ByteplusConfig(BaseModel):
    """BytePlus ModelArk provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "BytePlus ModelArk"
    PROVIDER_ID: str = "byteplus"
    ALIAS: str = "bpm"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://ark.ap-southeast.bytepluses.com/api/coding/v3"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class ByteplusMetadata(BaseModel):
    """BytePlus ModelArk UI display metadata."""

    name: str = "BytePlus ModelArk"
    color: str = "#2563EB"
    textIcon: str = "BP"
