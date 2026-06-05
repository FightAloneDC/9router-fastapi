"""Fal.ai model fetching — uses shared helper."""

from app.providers.fal_ai.config import FalAiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: FalAiConfig = FalAiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Fal.ai API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Fal.ai."""
    return await fetch_models_header_auth(_config, api_key)
