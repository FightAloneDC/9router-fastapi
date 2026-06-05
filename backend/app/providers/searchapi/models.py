"""SearchAPI model fetching — uses shared helper."""

from app.providers.searchapi.config import SearchapiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: SearchapiConfig = SearchapiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from SearchAPI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from SearchAPI."""
    return await fetch_models_header_auth(_config, api_key)
