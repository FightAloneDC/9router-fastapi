"""Exa model fetching — uses shared helper."""

from app.providers.exa.config import ExaConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: ExaConfig = ExaConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Exa API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Exa."""
    return await fetch_models_header_auth(_config, api_key)
