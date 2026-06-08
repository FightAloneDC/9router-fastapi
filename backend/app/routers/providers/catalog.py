"""Provider catalog endpoint — serves all provider metadata for frontend."""

from fastapi import APIRouter

from app.routers.providers._router import router
from app.services.catalog import collect_catalog, invalidate_catalog


@router.get("/providers/catalog")
async def providers_catalog():
    """Return full provider catalog for frontend consumption.

    Includes all provider metadata, categories, media kinds,
    compatible prefixes, and auth methods.
    """
    return collect_catalog()


@router.post("/providers/catalog/reload")
async def reload_catalog():
    """Force-reload the provider catalog cache.

    Call after adding/updating provider configs at runtime.
    """
    invalidate_catalog()
    catalog = collect_catalog(force=True)
    return {"success": True, "providerCount": len(catalog["providers"])}
