"""OAuth service module — Provider-Specific (PS) dispatch layer.

Provides handler-based dispatch for all OAuth operations.
Per-provider logic lives in backend/app/providers/<provider>/oauth.py.
PKCE utilities live in backend/app/utils/pkce.py.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _discover_oauth_handlers() -> dict[str, str]:
    """Auto-discover OAuth handlers from providers that have oauth.py.

    Iterates all sub-packages under app.providers and checks for an
    oauth.py module containing a class that inherits from BaseOAuthHandler.
    Only registers classes actually defined in that module (not imported).

    Returns dict mapping provider_id → "module.path.ClassName".
    """
    import app.providers as providers_pkg
    from app.providers.oauth_base import BaseOAuthHandler

    registry: dict[str, str] = {}
    for importer, modname, ispkg in pkgutil.iter_modules(providers_pkg.__path__):
        if not ispkg:
            continue
        module_path = f"app.providers.{modname}.oauth"
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            continue
        except Exception:
            logger.warning("Failed to import %s", module_path, exc_info=True)
            continue

        for attr_name, obj in inspect.getmembers(module, inspect.isclass):
            # Only register classes defined in THIS module, not re-imports
            if obj.__module__ != module_path:
                continue
            if (
                issubclass(obj, BaseOAuthHandler)
                and obj is not BaseOAuthHandler
                and getattr(obj, "PROVIDER_ID", None)
            ):
                registry[obj.PROVIDER_ID] = f"{module_path}.{attr_name}"

    return registry


_handler_cache: dict[str, Any] = {}
_handler_classes: dict[str, str] | None = None


def _get_handler_classes() -> dict[str, str]:
    global _handler_classes
    if _handler_classes is None:
        _handler_classes = _discover_oauth_handlers()
    return _handler_classes


def get_oauth_handler(provider_name: str):
    """Get OAuth handler instance for a provider (lazy-loaded, cached)."""
    if provider_name in _handler_cache:
        return _handler_cache[provider_name]

    classes = _get_handler_classes()
    class_path = classes.get(provider_name)
    if not class_path:
        raise ValueError(f"Unknown OAuth provider: {provider_name}")

    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    handler_class = getattr(module, class_name)
    handler = handler_class()
    _handler_cache[provider_name] = handler
    return handler


# ═══════════════════════════════════════════════════════════════════════════════
# Dispatch Functions
# Thin orchestrators used by routers and other modules
# ═══════════════════════════════════════════════════════════════════════════════


def generate_auth_data(provider_name: str, redirect_uri: str, meta: Optional[dict] = None) -> dict:
    """Generate auth data for a provider using handler dispatch.

    Returns dict with: authUrl, state, codeVerifier, codeChallenge, redirectUri, flowType
    """
    from app.utils.pkce import generate_pkce

    handler = get_oauth_handler(provider_name)
    pkce = generate_pkce()

    auth_url = None
    if handler.flow_type in ("authorization_code_pkce",):
        auth_url = handler.build_auth_url(redirect_uri, pkce["state"], pkce["codeChallenge"])
    elif handler.flow_type in ("authorization_code",):
        auth_url = handler.build_auth_url(redirect_uri, pkce["state"])
    # device_code and import_token have no auth_url

    return {
        "authUrl": auth_url,
        "state": pkce["state"],
        "codeVerifier": pkce["codeVerifier"],
        "codeChallenge": pkce["codeChallenge"],
        "redirectUri": redirect_uri,
        "flowType": handler.flow_type,
    }


async def exchange_tokens(
    provider_name: str,
    code: str,
    redirect_uri: str,
    code_verifier: str = "",
    state: str = "",
    meta: Optional[dict] = None,
) -> dict:
    """Exchange code for tokens using handler dispatch."""
    handler = get_oauth_handler(provider_name)

    tokens = await handler.exchange_code(code, redirect_uri, code_verifier, state)

    extra = None
    if hasattr(handler, "post_exchange"):
        try:
            extra = await handler.post_exchange(tokens)
        except NotImplementedError:
            pass

    return handler.map_tokens(tokens, extra)


async def request_device_code(
    provider_name: str,
    code_challenge: str = "",
    options: Optional[dict] = None,
) -> dict:
    """Request device code using handler dispatch."""
    handler = get_oauth_handler(provider_name)
    if handler.flow_type not in ("device_code", "polling"):
        raise ValueError(f"Provider {provider_name} does not support device code flow")
    return await handler.request_device_code(code_challenge, options)


async def poll_for_token(
    provider_name: str,
    device_code: str,
    code_verifier: str = "",
    extra_data: Optional[dict] = None,
) -> dict:
    """Poll for token using handler dispatch."""
    handler = get_oauth_handler(provider_name)
    if handler.flow_type not in ("device_code", "polling"):
        raise ValueError(f"Provider {provider_name} does not support device code flow")

    result = await handler.poll_token(device_code, code_verifier, extra_data)

    if result.get("ok"):
        data = result["data"]
        if data.get("access_token"):
            extra = None
            if hasattr(handler, "post_exchange"):
                try:
                    extra = await handler.post_exchange(data)
                except NotImplementedError:
                    pass
            return {"success": True, "tokens": handler.map_tokens(data, extra)}
        else:
            error = data.get("error", "")
            if error in ("authorization_pending", "slow_down"):
                return {
                    "success": False,
                    "error": error,
                    "errorDescription": data.get("error_description") or data.get("message"),
                    "pending": error == "authorization_pending",
                }
            return {
                "success": False,
                "error": error or "no_access_token",
                "errorDescription": data.get("error_description") or data.get("message") or "No access token received",
            }

    data = result.get("data", {})
    return {
        "success": False,
        "error": data.get("error", "unknown"),
        "errorDescription": data.get("error_description"),
    }


def map_tokens(provider_name: str, token_data: dict) -> dict:
    """Map provider tokens to standard format using handler dispatch."""
    handler = get_oauth_handler(provider_name)
    return handler.map_tokens(token_data)


async def refresh_access_token(
    provider: str,
    refresh_token: str,
    provider_specific_data: Optional[dict] = None,
) -> dict:
    """Refresh access token using handler dispatch."""
    handler = get_oauth_handler(provider)
    return await handler.refresh_token(refresh_token)
