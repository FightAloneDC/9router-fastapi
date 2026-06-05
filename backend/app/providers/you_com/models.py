"""You.com model fetching — uses shared helper."""

from app.providers.you_com.config import YouComConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: YouComConfig = YouComConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from You.com API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from You.com."""
    return await fetch_models_header_auth(_config, api_key)
