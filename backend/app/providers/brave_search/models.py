"""Brave Search model fetching — uses shared helper."""

from app.providers.brave_search.config import BraveSearchConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: BraveSearchConfig = BraveSearchConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Brave Search API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Brave Search."""
    return await fetch_models_header_auth(_config, api_key)
