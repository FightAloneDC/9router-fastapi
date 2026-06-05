"""xAI model fetching — uses shared helper."""

from app.providers.xai.config import XaiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: XaiConfig = XaiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from xAI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from xAI."""
    return await fetch_models_header_auth(_config, api_key)
