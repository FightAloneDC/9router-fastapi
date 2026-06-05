"""Nanobanana model fetching — uses shared helper."""

from app.providers.nanobanana.config import NanobananaConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: NanobananaConfig = NanobananaConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Nanobanana API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Nanobanana."""
    return await fetch_models_header_auth(_config, api_key)
