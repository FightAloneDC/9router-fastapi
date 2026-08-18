"""Morph model fetching — uses shared helper."""

from app.providers.model_helpers import fetch_models_header_auth
from app.providers.morph.config import MorphConfig

_config: MorphConfig = MorphConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Morph API response (OpenAI list shape)."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Morph."""
    return await fetch_models_header_auth(_config, api_key)
