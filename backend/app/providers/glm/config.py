"""GLM Coding provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GlmConfig(BaseProviderConfig):
    """GLM Coding provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "GLM Coding"
    PROVIDER_ID: str = "glm"
    ALIAS: str = "glm"
    BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    FORMAT: str = "claude"
    SERVICE_KINDS: list[str] = ["llm"]


class GlmMetadata(BaseMetadata):
    """GLM Coding UI display metadata."""

    name: str = "GLM Coding"
    color: str = "#2563EB"
    textIcon: str = "GL"
    icon: str = "Code"
    website: str = "https://open.bigmodel.cn"
    notice: dict | None = {"apiKeyUrl": "https://open.bigmodel.cn/usercenter/apikeys"}
