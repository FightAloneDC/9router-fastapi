"""Xiaomi MiMo (Token Plan) provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class XiaomiTokenplanConfig(BaseModel):
    """Xiaomi MiMo (Token Plan) provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Xiaomi MiMo (Token Plan)"
    PROVIDER_ID: str = "xiaomi-tokenplan"
    ALIAS: str = "xmtp"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.xiaomimimo.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class XiaomiTokenplanMetadata(BaseModel):
    """Xiaomi MiMo (Token Plan) UI display metadata."""

    name: str = "Xiaomi MiMo (Token Plan)"
    color: str = "#FF6700"
    textIcon: str = "XT"
