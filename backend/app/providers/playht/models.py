"""PlayHT model fetching — uses shared helper."""

from app.providers.playht.config import PlayhtConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: PlayhtConfig = PlayhtConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from PlayHT API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from PlayHT."""
    return await fetch_models_header_auth(_config, api_key)
