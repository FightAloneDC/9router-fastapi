"""Cartesia model fetching — uses shared helper."""

from app.providers.cartesia.config import CartesiaConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: CartesiaConfig = CartesiaConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Cartesia API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Cartesia."""
    return await fetch_models_header_auth(_config, api_key)
