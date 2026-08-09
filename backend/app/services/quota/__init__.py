"""Quota usage handler registry.

Maps provider IDs to their usage handler instances.
Providers without a handler return a "not supported" message.
"""

from __future__ import annotations

from .base import BaseUsageHandler, QuotaItem, UsageResponse
from .claude import ClaudeUsageHandler
from .codex import CodexUsageHandler
from .github import GitHubUsageHandler
from .kiro import KiroUsageHandler
from .qoder import QoderUsageHandler

_HANDLERS: dict[str, BaseUsageHandler] = {}


def _register(handler: BaseUsageHandler) -> None:
    _HANDLERS[handler.PROVIDER_ID] = handler


_register(GitHubUsageHandler())
_register(ClaudeUsageHandler())
_register(CodexUsageHandler())
_register(KiroUsageHandler())
_register(QoderUsageHandler())


def get_usage_handler(
    provider_id: str,
) -> BaseUsageHandler | None:
    """Return the usage handler for a provider, or None."""
    return _HANDLERS.get(provider_id)


def supported_providers() -> list[str]:
    """Return list of provider IDs with usage handlers."""
    return list(_HANDLERS.keys())


__all__ = [
    "BaseUsageHandler",
    "QuotaItem",
    "UsageResponse",
    "get_usage_handler",
    "supported_providers",
]
