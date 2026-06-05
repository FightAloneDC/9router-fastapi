"""Cohere model fetching — uses shared helper."""

from app.providers.cohere.config import CohereConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: CohereConfig = CohereConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Cohere API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Cohere."""
    return await fetch_models_header_auth(_config, api_key)
