"""Tavily model fetching — uses shared helper."""

from app.providers.tavily.config import TavilyConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: TavilyConfig = TavilyConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Tavily API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Tavily."""
    return await fetch_models_header_auth(_config, api_key)
