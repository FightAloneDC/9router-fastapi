"""Mistral provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MistralConfig(BaseProviderConfig):
    """Mistral provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Mistral"
    PROVIDER_ID: str = "mistral"
    ALIAS: str = "mi"
    BASE_URL: str = "https://api.mistral.ai/v1"
    SERVICE_KINDS: list[str] = ["llm", "imageToText", "embedding"]
    MODEL_CATALOG_TABLE: bool = True
    # Org-level. Public docs: RPS / TPM / tokens per month vary by
    # Studio plan (Free mode vs Scale tiers). Exact numbers are on
    # console Limits, not in the public table. Empty caps = tracker
    # uses local usage_history only.
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "free": {},
        "scale": {},
    }

    # ── Bulk Import ─────────────────────────────────────────────────────
    SUPPORTS_BULK_IMPORT: bool = True
    BULK_IMPORT_FORMAT: str = "farm-json"

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "mistral-embed": "embedding",
        "mistral-embed-2312": "embedding",
        "codestral-embed": "embedding",
        "codestral-embed-2505": "embedding",
    }


class MistralMetadata(BaseMetadata):
    """Mistral UI display metadata."""

    name: str = "Mistral"
    color: str = "#FF7000"
    textIcon: str = "MI"
    icon: str = "Wind"
    website: str = "https://console.mistral.ai"
    notice: dict | None = {
        "text": (
            "Limits are per organization (RPS / TPM / month). "
            "Exact caps: console Limits. Tracker used is local "
            "chat logs for this key; headers overlay if present."
        ),
        "apiKeyUrl": "https://console.mistral.ai/api-keys/",
    }
