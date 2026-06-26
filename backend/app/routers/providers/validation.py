"""Provider credential validation — dispatches to provider handlers."""

from app.providers.provider import Provider
from app.providers.base import ValidateResult
from app.schemas.provider import ProviderValidateResponse


async def _validate_provider(provider: str, api_key: str, data: dict | None = None) -> ProviderValidateResponse:
    """Validate provider credentials using provider handler."""
    # Check if this is a compatible provider node
    import json as _json
    from sqlalchemy import select
    from app.models.provider import ProviderNode
    from app.database import async_session

    async with async_session() as db:
        node_result = await db.execute(
            select(ProviderNode).where(ProviderNode.id == provider)
        )
        node = node_result.scalar_one_or_none()

    if node:
        node_data = {}
        try:
            node_data = _json.loads(node.data) if node.data else {}
        except (_json.JSONDecodeError, TypeError):
            pass

        base_url = node_data.get("baseUrl", "")
        extra_headers = node_data.get("extraHeaders")

        if node.type == "anthropic-compatible":
            return await _validate_custom_anthropic(api_key, base_url)
        else:
            return await _validate_custom_openai(api_key, base_url, extra_headers)

    # Built-in provider
    try:
        p = Provider(provider)
        handler = p.handler()
        result = await handler.validate(api_key, data)
        return ProviderValidateResponse(
            valid=result.valid,
            error=result.error,
            models=result.models,
        )
    except (ValueError, ModuleNotFoundError):
        return ProviderValidateResponse(
            valid=False,
            error=f"Unknown provider: {provider}",
        )


async def _validate_custom_openai(
    api_key: str, base_url: str, extra_headers: dict | None = None
) -> ProviderValidateResponse:
    """Validate a custom OpenAI-compatible endpoint (GET /models + Bearer auth)."""
    from app.providers.base import BaseProviderConfig, BaseProviderHandler

    config = BaseProviderConfig(
        PROVIDER_NAME="custom",
        PROVIDER_ID="custom",
        ALIAS="custom",
        BASE_URL=base_url,
        EXTRA_HEADERS=extra_headers or {},
    )
    handler = BaseProviderHandler(config)
    result = await handler.validate(api_key)
    return ProviderValidateResponse(
        valid=result.valid,
        error=result.error,
        models=result.models,
    )


async def _validate_custom_anthropic(
    api_key: str, base_url: str
) -> ProviderValidateResponse:
    """Validate a custom Anthropic-compatible endpoint (GET /models + x-api-key)."""
    from app.providers.base import BaseProviderConfig, BaseProviderHandler

    config = BaseProviderConfig(
        PROVIDER_NAME="custom-anthropic",
        PROVIDER_ID="custom-anthropic",
        ALIAS="custom-anthropic",
        BASE_URL=base_url,
    )
    handler = BaseProviderHandler(config)
    result = await handler._validate_anthropic_compatible(api_key, base_url)
    return ProviderValidateResponse(
        valid=result.valid,
        error=result.error,
        models=result.models,
    )
