"""Stability AI model fetching — uses shared helper."""

from app.providers.stability_ai.config import StabilityAiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: StabilityAiConfig = StabilityAiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Stability AI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Stability AI."""
    return await fetch_models_header_auth(_config, api_key)
