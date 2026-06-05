"""Xiaomi MiMo model fetching — uses shared helper."""

from app.providers.xiaomi_mimo.config import XiaomiMimoConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: XiaomiMimoConfig = XiaomiMimoConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Xiaomi MiMo API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Xiaomi MiMo."""
    return await fetch_models_header_auth(_config, api_key)
