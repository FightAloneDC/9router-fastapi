"""GLM (China) provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GlmCnConfig(BaseProviderConfig):
    """GLM (China) provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "GLM (China)"
    PROVIDER_ID: str = "glm-cn"
    ALIAS: str = "glm-cn"
    BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    SERVICE_KINDS: list[str] = ["llm"]


class GlmCnMetadata(BaseMetadata):
    """GLM (China) UI display metadata."""

    name: str = "GLM (China)"
    color: str = "#DC2626"
    textIcon: str = "GC"
