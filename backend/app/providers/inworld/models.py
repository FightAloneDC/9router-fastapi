"""Inworld AI model fetching — uses shared helper."""

from app.providers.inworld.config import InworldConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: InworldConfig = InworldConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Inworld AI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Inworld AI."""
    return await fetch_models_header_auth(_config, api_key)
