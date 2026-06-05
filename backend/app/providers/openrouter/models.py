"""OpenRouter model fetching — uses shared helper."""

from app.providers.openrouter.config import OpenrouterConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: OpenrouterConfig = OpenrouterConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from OpenRouter API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from OpenRouter."""
    return await fetch_models_header_auth(_config, api_key)
