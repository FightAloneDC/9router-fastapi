"""Cerebras model fetching — uses shared helper."""

from app.providers.cerebras.config import CerebrasConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: CerebrasConfig = CerebrasConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Cerebras API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Cerebras."""
    return await fetch_models_header_auth(_config, api_key)
