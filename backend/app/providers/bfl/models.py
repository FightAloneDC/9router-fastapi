"""Black Forest Labs model fetching — uses shared helper."""

from app.providers.bfl.config import BflConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: BflConfig = BflConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Black Forest Labs API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Black Forest Labs."""
    return await fetch_models_header_auth(_config, api_key)
