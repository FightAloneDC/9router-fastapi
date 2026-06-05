"""Together model fetching — uses shared helper."""

from app.providers.together.config import TogetherConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: TogetherConfig = TogetherConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Together API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Together."""
    return await fetch_models_header_auth(_config, api_key)
