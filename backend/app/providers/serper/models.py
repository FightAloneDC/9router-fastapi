"""Serper model fetching — uses shared helper."""

from app.providers.serper.config import SerperConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: SerperConfig = SerperConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Serper API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Serper."""
    return await fetch_models_header_auth(_config, api_key)
