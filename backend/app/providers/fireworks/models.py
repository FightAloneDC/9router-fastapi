"""Fireworks model fetching — uses shared helper."""

from app.providers.fireworks.config import FireworksConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: FireworksConfig = FireworksConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Fireworks API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Fireworks."""
    return await fetch_models_header_auth(_config, api_key)
