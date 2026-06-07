"""Provider credential validation — dispatches to provider handlers."""

from app.providers.provider import Provider
from app.providers.base import ValidateResult
from app.schemas.provider import ProviderValidateResponse


async def _validate_provider(provider: str, api_key: str, data: dict | None = None) -> ProviderValidateResponse:
    """Validate provider credentials using provider handler."""
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


async def _validate_openai_compatible(
    api_key: str, base_url: str, extra_headers: dict | None = None
) -> ProviderValidateResponse:
    """Legacy wrapper — validates an OpenAI-compatible endpoint directly."""
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


# Keep individual functions as thin wrappers for backward compatibility
# during migration. These will be removed once all callers are updated.

async def _validate_anthropic(api_key: str, base_url: str | None = None) -> ProviderValidateResponse:
    data = {"baseUrl": base_url} if base_url else {}
    return await _validate_provider("anthropic", api_key, data)


async def _validate_google(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("gemini", api_key)


async def _validate_azure(api_key: str, extra_data: dict) -> ProviderValidateResponse:
    return await _validate_provider("azure", api_key, extra_data)


async def _validate_cloudflare(api_key: str, extra_data: dict) -> ProviderValidateResponse:
    return await _validate_provider("cloudflare-ai", api_key, extra_data)


async def _validate_openai_chat(api_key: str, base_url: str) -> ProviderValidateResponse:
    return await _validate_provider("kilo-gateway", api_key, {"baseUrl": base_url})


async def _validate_ollama(base_url: str) -> ProviderValidateResponse:
    return await _validate_provider("ollama", api_key="", data={"baseUrl": base_url})


async def _validate_vertex(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("vertex", api_key)


async def _validate_noauth() -> ProviderValidateResponse:
    return await _validate_provider("edge-tts", api_key="")


async def _validate_elevenlabs(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("elevenlabs", api_key)


async def _validate_deepgram(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("deepgram", api_key)


async def _validate_inworld(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("inworld", api_key)


async def _validate_voyage(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("voyage-ai", api_key)


async def _validate_assemblyai(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("assemblyai", api_key)


async def _validate_minimax(api_key: str, region: str = "minimax") -> ProviderValidateResponse:
    provider = "minimax-cn" if region == "minimax-cn" else "minimax"
    return await _validate_provider(provider, api_key)
