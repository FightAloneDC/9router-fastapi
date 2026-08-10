"""Provider catalog service — collects all provider metadata for frontend.

Discovers all provider sub-packages under app.providers, loads their
Config + Metadata + OAuth handler (if present), and returns a unified
catalog dict.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any

from app.providers.base import BaseMetadata, BaseProviderConfig

logger = logging.getLogger(__name__)

# ── Compatible prefixes ────────────────────────────────────────────────────
_COMPATIBLE_PREFIXES = {
    "openai": "openai-compatible-",
    "anthropic": "anthropic-compatible-",
    "customEmbedding": "custom-embedding-",
}

# ── Media kinds (static — not provider-specific) ───────────────────────────
_MEDIA_KINDS = [
    {"id": "embedding", "label": "Embedding", "icon": "Binary", "endpoint": {"method": "POST", "path": "/v1/embeddings"}},
    {"id": "rerank", "label": "Rerank", "icon": "ArrowUpDown", "endpoint": {"method": "POST", "path": "/v1/rerank"}},
    {"id": "tts", "label": "Text To Speech", "icon": "Volume2", "endpoint": {"method": "POST", "path": "/v1/audio/speech"}},
    {"id": "stt", "label": "Speech To Text", "icon": "Mic", "endpoint": {"method": "POST", "path": "/v1/audio/transcriptions"}},
    {"id": "webSearch", "label": "Web Search", "icon": "Search", "endpoint": {"method": "POST", "path": "/v1/search"}},
    {"id": "webFetch", "label": "Web Fetch", "icon": "Globe", "endpoint": {"method": "POST", "path": "/v1/web/fetch"}},
    {"id": "image", "label": "Text to Image", "icon": "Image", "endpoint": {"method": "POST", "path": "/v1/images/generations"}},
    {"id": "imageToText", "label": "Image to Text", "icon": "Eye", "endpoint": {"method": "POST", "path": "/v1/images/understanding"}},
    {"id": "video", "label": "Video", "icon": "Video", "endpoint": {"method": "POST", "path": "/v1/video/generations"}},
    {"id": "music", "label": "Music", "icon": "Music", "endpoint": {"method": "POST", "path": "/v1/audio/music"}},
]

_AUTH_METHODS = {
    "oauth": {"id": "oauth", "name": "OAuth", "icon": "Lock"},
    "apikey": {"id": "apikey", "name": "API Key", "icon": "Key"},
    "cookie": {"id": "cookie", "name": "Browser Cookie", "icon": "Cookie"},
}


def _discover_provider_folders() -> list[str]:
    """Discover all provider sub-package names under app.providers."""
    import app.providers as providers_pkg

    folders = []
    for _importer, modname, ispkg in pkgutil.iter_modules(providers_pkg.__path__):
        if ispkg:
            folders.append(modname)
    return sorted(folders)


def _load_provider_config(folder_name: str) -> BaseProviderConfig | None:
    """Load provider config class from a folder."""
    try:
        module = importlib.import_module(f"app.providers.{folder_name}.config")
        for attr in dir(module):
            cls = getattr(module, attr)
            if (
                isinstance(cls, type)
                and issubclass(cls, BaseProviderConfig)
                and cls is not BaseProviderConfig
                and attr.endswith("Config")
            ):
                return cls()
    except (ModuleNotFoundError, ValueError, Exception) as e:
        logger.debug("Cannot load config for %s: %s", folder_name, e)
    return None


def _load_provider_metadata(folder_name: str) -> BaseMetadata | None:
    """Load provider metadata class from a folder."""
    try:
        module = importlib.import_module(f"app.providers.{folder_name}.config")
        for attr in dir(module):
            cls = getattr(module, attr)
            if (
                isinstance(cls, type)
                and issubclass(cls, BaseMetadata)
                and cls is not BaseMetadata
                and attr.endswith("Metadata")
            ):
                return cls()
    except (ModuleNotFoundError, ValueError, Exception) as e:
        logger.debug("Cannot load metadata for %s: %s", folder_name, e)
    return None


def _try_get_oauth_flow_type(provider_id: str) -> str | None:
    """Try to get OAuth flow type for a provider (no error if not found)."""
    try:
        from app.services.oauth import get_oauth_handler
        handler = get_oauth_handler(provider_id)
        return handler.flow_type
    except (ValueError, ModuleNotFoundError):
        return None


def _derive_auth_type(config: BaseProviderConfig, flow_type: str | None) -> str:
    """Derive frontend authType from config and OAuth handler."""
    if config.CATEGORY == "webCookie":
        return "cookie"
    if flow_type:
        return "oauth"
    if config.NO_AUTH:
        return "free"
    return "apikey"


def _derive_category(config: BaseProviderConfig, flow_type: str | None) -> str:
    """Derive frontend category from provider config.CATEGORY field.

    If CATEGORY is set on the config, use it directly.
    Otherwise derive from auth properties.
    """
    if config.CATEGORY:
        return config.CATEGORY
    if flow_type:
        return "oauth"
    return "apiKey"


def _build_provider_entry(
    config: BaseProviderConfig,
    metadata: BaseMetadata,
    flow_type: str | None,
) -> dict[str, Any]:
    """Build a single provider catalog entry."""
    auth_type = _derive_auth_type(config, flow_type)

    # hasProviderSpecificData: providers that need extra form fields in AddKeyModal
    has_psd = bool(config.REGIONS) or config.PROVIDER_SPECIFIC_DATA

    return {
        "id": config.PROVIDER_ID,
        "alias": config.ALIAS,
        "name": metadata.name,
        "color": metadata.color,
        "textIcon": metadata.textIcon,
        "icon": metadata.icon,
        "website": metadata.website,
        "notice": metadata.notice,
        "authHint": metadata.authHint,
        "serviceKinds": config.SERVICE_KINDS or ["llm"],
        "flowType": flow_type,
        "authType": auth_type,
        "deprecated": config.DEPRECATED,
        "deprecationNotice": config.DEPRECATION_NOTICE,
        "hidden": config.HIDDEN,
        "noAuth": config.NO_AUTH,
        "passthroughModels": config.PASSTHROUGH_MODELS,
        "hasProviderSpecificData": has_psd,
        "regions": config.REGIONS,
        "defaultRegion": config.DEFAULT_REGION,
        "thinkingConfig": config.THINKING_CONFIG,
        "mediaPriority": config.MEDIA_PRIORITY,
        "modelsFetcher": config.MODELS_FETCHER,
        "supportsPAT": config.SUPPORTS_PAT,
        "supportsBulkImport": config.SUPPORTS_BULK_IMPORT,
        "bulkImportFormat": config.BULK_IMPORT_FORMAT,
        "requiresProxy": config.REQUIRES_PROXY,
        "customModal": config.CUSTOM_MODAL or None,
    }


# ── Public API ─────────────────────────────────────────────────────────────

_catalog_cache: dict[str, Any] | None = None


def collect_catalog(*, force: bool = False) -> dict[str, Any]:
    """Collect the full provider catalog.

    Returns a dict with keys: providers, categories, mediaKinds,
    compatiblePrefixes, authMethods.
    """
    global _catalog_cache
    if _catalog_cache is not None and not force:
        return _catalog_cache

    providers: dict[str, dict] = {}
    categories: dict[str, list[str]] = {
        "free": [], "freeTier": [], "oauth": [], "apiKey": [], "webCookie": [],
    }

    for folder_name in _discover_provider_folders():
        config = _load_provider_config(folder_name)
        metadata = _load_provider_metadata(folder_name)

        if config is None or metadata is None:
            continue

        provider_id = config.PROVIDER_ID
        flow_type = _try_get_oauth_flow_type(provider_id)
        entry = _build_provider_entry(config, metadata, flow_type)
        providers[provider_id] = entry

        category = _derive_category(config, flow_type)
        categories[category].append(provider_id)

    catalog = {
        "providers": providers,
        "categories": categories,
        "mediaKinds": _MEDIA_KINDS,
        "compatiblePrefixes": _COMPATIBLE_PREFIXES,
        "authMethods": _AUTH_METHODS,
    }

    _catalog_cache = catalog
    return catalog


def invalidate_catalog() -> None:
    """Invalidate the catalog cache (for hot-reload)."""
    global _catalog_cache
    _catalog_cache = None
