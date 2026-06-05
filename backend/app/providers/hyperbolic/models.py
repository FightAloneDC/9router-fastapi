"""Hyperbolic model fetching — uses shared helper."""

from app.providers.hyperbolic.config import HyperbolicConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: HyperbolicConfig = HyperbolicConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Hyperbolic API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Hyperbolic."""
    return await fetch_models_header_auth(_config, api_key)
