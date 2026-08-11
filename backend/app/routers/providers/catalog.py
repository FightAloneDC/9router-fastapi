"""Provider catalog endpoint — serves all provider metadata for frontend."""

from fastapi import HTTPException

from app.routers.providers._router import router
from app.services.catalog import collect_catalog, invalidate_catalog


@router.get("/providers/catalog")
async def providers_catalog():
    """Return full provider catalog for frontend consumption.

    Includes all provider metadata, categories, media kinds,
    compatible prefixes, and auth methods.
    """
    return collect_catalog()


@router.get("/providers/catalog/{provider_id}")
async def provider_catalog_entry(provider_id: str):
    """Return catalog metadata for a single provider (detail pages).

    `provider_id` may be a provider id or alias.
    """
    catalog = collect_catalog()
    providers = catalog["providers"]
    entry = providers.get(provider_id)
    if entry is None:
        for candidate in providers.values():
            if candidate.get("alias") == provider_id:
                entry = candidate
                break
    if entry is None:
        raise HTTPException(status_code=404, detail="Provider not in catalog")
    return {
        "provider": entry,
        "compatiblePrefixes": catalog["compatiblePrefixes"],
        "authMethods": catalog["authMethods"],
    }


@router.post("/providers/catalog/reload")
async def reload_catalog():
    """Force-reload the provider catalog cache.

    Call after adding/updating provider configs at runtime.
    """
    invalidate_catalog()
    catalog = collect_catalog(force=True)
    return {"success": True, "providerCount": len(catalog["providers"])}
