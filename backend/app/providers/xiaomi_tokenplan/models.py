"""Xiaomi MiMo (Token Plan) model fetching — region-aware URLs."""

import httpx

from app.providers.xiaomi_tokenplan.config import XiaomiTokenplanConfig
from app.providers.model_helpers import fetch_models_header_auth
from app.providers.base import BaseProviderConfig

_config: XiaomiTokenplanConfig = XiaomiTokenplanConfig()

# Region-specific base URLs
_REGION_URLS: dict[str, str] = {
    "sgp": "https://token-plan-sgp.xiaomimimo.com/v1",
    "cn": "https://token-plan-cn.xiaomimimo.com/v1",
    "ams": "https://token-plan-ams.xiaomimimo.com/v1",
}


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Xiaomi MiMo (Token Plan) API response."""
    return data.get("data", [])


async def fetch_models(api_key: str, region: str = "sgp") -> list[dict]:
    """Fetch available models from Xiaomi MiMo (Token Plan).

    Supports region-specific URLs (sgp, cn, ams).
    """
    base_url: str = _REGION_URLS.get(region, _REGION_URLS["sgp"])
    config = BaseProviderConfig(
        PROVIDER_NAME=_config.PROVIDER_NAME,
        PROVIDER_ID=_config.PROVIDER_ID,
        ALIAS=_config.ALIAS,
        BASE_URL=base_url,
    )
    return await fetch_models_header_auth(config, api_key)
