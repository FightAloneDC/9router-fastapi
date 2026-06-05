"""Recraft model fetching — uses shared helper."""

from app.providers.recraft.config import RecraftConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: RecraftConfig = RecraftConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Recraft API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Recraft."""
    return await fetch_models_header_auth(_config, api_key)
