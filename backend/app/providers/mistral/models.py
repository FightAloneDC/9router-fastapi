"""Mistral model fetching — uses shared helper."""

from app.providers.mistral.config import MistralConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: MistralConfig = MistralConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Mistral API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Mistral."""
    return await fetch_models_header_auth(_config, api_key)
