"""GLM Coding provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class GLMConfig(BaseModel):
    """GLM Coding provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "GLM Coding"
    PROVIDER_ID: str = "glm"
    ALIAS: str = "glm"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class GLMMetadata(BaseModel):
    """GLM Coding UI display metadata."""

    name: str = "GLM Coding"
    color: str = "#2563EB"
    textIcon: str = "GL"
