"""Alibaba model fetching — uses shared helper."""

from app.providers.alicode.config import AlicodeConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: AlicodeConfig = AlicodeConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Alibaba API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Alibaba."""
    return await fetch_models_header_auth(_config, api_key)
