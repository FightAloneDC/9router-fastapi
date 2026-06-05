"""Firecrawl model fetching — uses shared helper."""

from app.providers.firecrawl.config import FirecrawlConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: FirecrawlConfig = FirecrawlConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Firecrawl API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Firecrawl."""
    return await fetch_models_header_auth(_config, api_key)
