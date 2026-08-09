"""Quota usage handler registry.

Discovers usage handlers from provider modules (PS rule): each
provider that supports quota tracking ships a `quota.py` in its
own folder (app.providers.<provider>.quota) defining a
BaseUsageHandler subclass. Providers without one return a
"not supported" message.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from .base import BaseUsageHandler, QuotaItem, UsageResponse

logger = logging.getLogger(__name__)

_HANDLERS: dict[str, BaseUsageHandler] = {}


def _discover_provider_folders() -> list[str]:
    """List all provider sub-package names under app.providers."""
    import app.providers as providers_pkg

    return [
        modname
        for _importer, modname, ispkg
        in pkgutil.iter_modules(providers_pkg.__path__)
        if ispkg
    ]


def _load_usage_handler(
    folder_name: str,
) -> BaseUsageHandler | None:
    """Load the usage handler from a provider folder, if any."""
    try:
        module = importlib.import_module(
            f"app.providers.{folder_name}.quota"
        )
    except ModuleNotFoundError:
        return None
    except Exception as e:
        logger.warning(
            "Cannot load quota handler for %s: %s",
            folder_name, e,
        )
        return None

    for attr in dir(module):
        cls = getattr(module, attr)
        if (
            isinstance(cls, type)
            and issubclass(cls, BaseUsageHandler)
            and cls.__module__ == module.__name__
        ):
            return cls()
    return None


for _folder in _discover_provider_folders():
    _handler = _load_usage_handler(_folder)
    if _handler is not None:
        _HANDLERS[_handler.PROVIDER_ID] = _handler


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
