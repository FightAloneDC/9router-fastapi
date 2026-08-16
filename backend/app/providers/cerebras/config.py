"""Cerebras provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CerebrasConfig(BaseProviderConfig):
    """Cerebras provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cerebras"
    PROVIDER_ID: str = "cerebras"
    ALIAS: str = "cb"
    BASE_URL: str = "https://api.cerebras.ai/v1"
    SERVICE_KINDS: list[str] = ["llm"]
    MODEL_CATALOG_TABLE: bool = True
    # Org-level, per model. Docs:
    # inference-docs.cerebras.ai/support/rate-limits
    # free = Free Trial; payg = Developer (no TPH/TPD).
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "free/gpt-oss-120b": {
            "rpm": 5, "tpm": 30000,
            "tph": 1000000, "tpd": 1000000,
        },
        "free/zai-glm-4.7": {
            "rpm": 5, "tpm": 30000,
            "tph": 1000000, "tpd": 1000000,
        },
        "free/gemma-4-31b": {
            "rpm": 5, "tpm": 30000,
            "tph": 1000000, "tpd": 1000000,
        },
        "payg/gpt-oss-120b": {
            "rpm": 1000, "tpm": 1000000,
        },
        "payg/zai-glm-4.7": {
            "rpm": 500, "tpm": 500000,
        },
        "payg/gemma-4-31b": {
            "rpm": 300, "tpm": 500000,
        },
    }


class CerebrasMetadata(BaseMetadata):
    """Cerebras UI display metadata."""

    name: str = "Cerebras"
    color: str = "#FF6B00"
    textIcon: str = "CB"
    icon: str = "Cpu"
    website: str = "https://cloud.cerebras.ai"
    notice: dict | None = {
        "text": (
            "Free Trial: 5 RPM / 30K TPM per model (org-level). "
            "Developer (payg) raises RPM/TPM and drops hourly/"
            "daily caps. Exact org: cloud.cerebras.ai limits."
        ),
        "apiKeyUrl": "https://cloud.cerebras.ai/",
    }
