"""Alibaba Studio provider definition.

Model Studio Intl — standard DashScope API keys (sk-...), NOT Coding
Plan keys.  Sibling of alicode-intl (Coding Plan).  Two key types use
two different hosts.

Static provider characteristics — runtime data (API keys, custom
baseUrl) come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AlimsIntlConfig(BaseProviderConfig):
    """Alibaba Studio provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Alibaba Studio"
    PROVIDER_ID: str = "alims-intl"
    ALIAS: str = "alims-intl"
    BASE_URL: str = (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    SERVICE_KINDS: list[str] = ["llm", "rerank"]

    # ── Bulk Import ─────────────────────────────────────────────────────
    SUPPORTS_BULK_IMPORT: bool = True
    BULK_IMPORT_FORMAT: str = "farm-json"


class AlimsIntlMetadata(BaseMetadata):
    """Alibaba Studio UI display metadata."""

    name: str = "Alibaba Studio"
    color: str = "#FF6A00"
    textIcon: str = "ALi"
    icon: str = "Cloud"
    website: str = "https://modelstudio.console.alibabacloud.com"
    notice: dict | None = {
        "apiKeyUrl": (
            "https://modelstudio.console.alibabacloud.com/?apiKey=1"
        )
    }
