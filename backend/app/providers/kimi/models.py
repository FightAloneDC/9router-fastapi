"""Kimi model fetching — uses shared helper."""

from app.providers.kimi.config import KimiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: KimiConfig = KimiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Kimi API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Kimi."""
    return await fetch_models_header_auth(_config, api_key)
