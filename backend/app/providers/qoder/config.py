"""Qoder provider definition.

Static provider characteristics — runtime data (OAuth tokens, PAT tokens)
come from ProviderConnection.data in the database.

⚠️  CRITICAL: Do NOT modify this provider without user approval.
    Extensive investigation and trial-error has been done.
    See docs/archives/qoder-docs/BUG-FIXING-LOG.md before making any changes.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class QoderConfig(BaseProviderConfig):
    """Qoder provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Qoder"
    PROVIDER_ID: str = "qoder"
    ALIAS: str = "qd"
    BASE_URL: str = "https://api3.qoder.sh"
    SERVICE_KINDS: list[str] = ["llm"]

    # ── Connection defaults ─────────────────────────────────────────────
    FORMAT: str = "qoder"  # Custom format — not OpenAI-compatible
    VALIDATION_TYPE: str = "qoder"
    SUPPORTS_PAT: bool = True
    # Accepts bulk JSON account import (grok-farm-modular export)
    SUPPORTS_BULK_IMPORT: bool = True
    # Fetch/set/clear → provider_models (not connection data.models).
    MODEL_CATALOG_TABLE: bool = True
    # Per-account trial (operator 2026-08-18 + quota API shape):
    # 300 credits, window window ~14 days (expiresAt from upstream).
    # No published RPM/TPM table — do not invent rows.
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "trial": {"credits": 300, "days": 14},
    }


class QoderMetadata(BaseMetadata):
    """Qoder UI display metadata."""

    name: str = "Qoder"
    color: str = "#6366F1"
    textIcon: str = "QD"
    icon: str = "Zap"
    website: str = "https://qoder.com"
    notice: dict | None = {
        "text": (
            "Trial: 300 credits per account/connection, "
            "valid ~14 days (see expiresAt on quota API). "
            "Live used/remaining: Quota Tracker / "
            "openapi…/quota/usage."
        ),
        "signupUrl": "https://qoder.com",
    }
