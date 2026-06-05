"""Runway ML model fetching — uses shared helper."""

from app.providers.runwayml.config import RunwaymlConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: RunwaymlConfig = RunwaymlConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Runway ML API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Runway ML."""
    return await fetch_models_header_auth(_config, api_key)
