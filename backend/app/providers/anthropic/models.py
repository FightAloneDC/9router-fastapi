"""Anthropic model fetching — uses shared helper."""

from app.providers.anthropic.config import AnthropicConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: AnthropicConfig = AnthropicConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Anthropic API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Anthropic."""
    return await fetch_models_header_auth(_config, api_key)
