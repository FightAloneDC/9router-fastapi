"""Provider catalog endpoint — serves all provider metadata for frontend."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.providers._router import router
from app.services.catalog import collect_catalog, invalidate_catalog
from app.services.provider_aliases import refresh_from_db
from app.services.proxy import display_alias


async def _catalog_with_db_prefix(db: AsyncSession) -> dict:
    """Config catalog with DB prefix overlay (missing row = config)."""
    await refresh_from_db(db)
    catalog = collect_catalog()
    providers = {
        pid: {**entry, "alias": display_alias(pid)}
        for pid, entry in catalog["providers"].items()
    }
    return {**catalog, "providers": providers}


@router.get("/providers/catalog")
async def providers_catalog(db: AsyncSession = Depends(get_db)):
    """Return full provider catalog for frontend consumption.

    Includes all provider metadata, categories, media kinds,
    compatible prefixes, and auth methods.
    """
    return await _catalog_with_db_prefix(db)


@router.get("/providers/catalog/{provider_id}")
async def provider_catalog_entry(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return catalog metadata for a single provider (detail pages).

    `provider_id` may be a provider id or prefix.
    """
    catalog = await _catalog_with_db_prefix(db)
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
async def reload_catalog(db: AsyncSession = Depends(get_db)):
    """Force-reload the provider catalog cache.

    Call after adding/updating provider configs at runtime.
    """
    invalidate_catalog()
    catalog = await _catalog_with_db_prefix(db)
    return {"success": True, "providerCount": len(catalog["providers"])}
