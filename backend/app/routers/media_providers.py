"""Media providers API — providers filtered by service kind."""

from fastapi import APIRouter, HTTPException

from app.providers import AVAILABLE_PROVIDERS
from app.providers.provider import Provider

router = APIRouter(tags=["media-providers"])


def _get_provider_service_kinds(provider_id: str) -> list[str]:
    """Get serviceKinds for a provider, with fallback."""
    try:
        p = Provider(provider_id)
        return p.config().SERVICE_KINDS or ["llm"]
    except (ValueError, ModuleNotFoundError):
        return ["llm"]


def _get_provider_meta_from_config(provider_id: str) -> dict:
    """Get provider metadata from Provider class."""
    try:
        p = Provider(provider_id)
        meta = p.metadata()
        return {"name": meta.name, "color": meta.color, "textIcon": meta.textIcon}
    except (ValueError, ModuleNotFoundError):
        return {"name": provider_id, "color": "#888888", "textIcon": provider_id[:2].upper()}


VALID_KINDS: set[str] = {"embedding", "rerank", "tts", "stt", "webSearch", "webFetch", "image", "imageToText", "video", "music"}


@router.get("/media-providers/{kind}")
async def list_media_providers(kind: str):
    """List providers that support a given service kind."""
    if kind not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid kind '{kind}'. Valid: {', '.join(sorted(VALID_KINDS))}",
        )

    result: list[dict] = []
    for provider_id in AVAILABLE_PROVIDERS:
        kinds: list[str] = _get_provider_service_kinds(provider_id)
        if kind not in kinds:
            continue

        meta: dict = _get_provider_meta_from_config(provider_id)
        result.append({
            "id": provider_id,
            "name": meta.get("name", provider_id),
            "color": meta.get("color", "#888888"),
            "textIcon": meta.get("textIcon", provider_id[:2].upper()),
            "serviceKinds": kinds,
        })

    result.sort(key=lambda x: x.get("name", ""))
    return result


@router.get("/media-providers")
async def list_all_media_providers():
    """List all media providers grouped by kind."""
    result: dict[str, list] = {}

    for kind in sorted(VALID_KINDS):
        providers: list[dict] = []
        for provider_id in AVAILABLE_PROVIDERS:
            kinds: list[str] = _get_provider_service_kinds(provider_id)
            if kind not in kinds:
                continue

            meta: dict = _get_provider_meta_from_config(provider_id)
            providers.append({
                "id": provider_id,
                "name": meta.get("name", provider_id),
                "color": meta.get("color", "#888888"),
                "textIcon": meta.get("textIcon", provider_id[:2].upper()),
                "serviceKinds": kinds,
            })

        providers.sort(key=lambda x: x.get("name", ""))
        result[kind] = providers

    return result
