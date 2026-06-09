"""Qwen Code provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class QwenConfig(BaseProviderConfig):
    """Qwen Code provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Qwen Code"
    PROVIDER_ID: str = "qwen"
    ALIAS: str = "qw"
    BASE_URL: str = "https://chat.qwen.ai"
    SERVICE_KINDS: list[str] = ["llm"]
    CATEGORY: str = "free"
    DEPRECATED: bool = True
    HIDDEN: bool = True
    DEPRECATION_NOTICE: str = "Qwen OAuth free tier was discontinued by Alibaba on 2026-04-15. New connections will not work."


class QwenMetadata(BaseMetadata):
    """Qwen Code UI display metadata."""

    name: str = "Qwen Code"
    color: str = "#10B981"
    textIcon: str = "QW"
    icon: str = "Brain"
    website: str = "https://chat.qwen.ai"
    notice: dict | None = {"signupUrl": "https://chat.qwen.ai"}
