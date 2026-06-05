"""SiliconFlow provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class SiliconflowConfig(BaseProviderConfig):
    """SiliconFlow provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "SiliconFlow"
    PROVIDER_ID: str = "siliconflow"
    ALIAS: str = "sf"
    BASE_URL: str = "https://api.siliconflow.com/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "image", "tts"]


class SiliconflowMetadata(BaseMetadata):
    """SiliconFlow UI display metadata."""

    name: str = "SiliconFlow"
    color: str = "#000000"
    textIcon: str = "SF"
