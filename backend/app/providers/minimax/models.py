"""Minimax Coding model fetching — uses shared helper."""

from app.providers.minimax.config import MinimaxConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: MinimaxConfig = MinimaxConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Minimax Coding API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Minimax Coding."""
    return await fetch_models_header_auth(_config, api_key)
