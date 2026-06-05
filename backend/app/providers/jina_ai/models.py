"""Jina AI model fetching — uses shared helper."""

from app.providers.jina_ai.config import JinaAiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: JinaAiConfig = JinaAiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Jina AI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Jina AI."""
    return await fetch_models_header_auth(_config, api_key)
