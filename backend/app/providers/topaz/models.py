"""Topaz model fetching — uses shared helper."""

from app.providers.topaz.config import TopazConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: TopazConfig = TopazConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Topaz API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Topaz."""
    return await fetch_models_header_auth(_config, api_key)
