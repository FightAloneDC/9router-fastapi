"""GLM (China) provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class GLMCNConfig(BaseModel):
    """GLM (China) provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "GLM (China)"
    PROVIDER_ID: str = "glm-cn"
    ALIAS: str = "glm-cn"

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


class GLMCNMetadata(BaseModel):
    """GLM (China) UI display metadata."""

    name: str = "GLM (China)"
    color: str = "#DC2626"
    textIcon: str = "GC"
