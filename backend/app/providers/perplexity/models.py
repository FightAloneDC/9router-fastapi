"""Perplexity model fetching — uses shared helper."""

from app.providers.perplexity.config import PerplexityConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: PerplexityConfig = PerplexityConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Perplexity API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Perplexity."""
    return await fetch_models_header_auth(_config, api_key)
