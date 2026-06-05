"""Nebius AI model fetching — uses shared helper."""

from app.providers.nebius.config import NebiusConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: NebiusConfig = NebiusConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Nebius AI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Nebius AI."""
    return await fetch_models_header_auth(_config, api_key)
