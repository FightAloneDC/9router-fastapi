"""Alibaba Intl model fetching — uses shared helper."""

from app.providers.alicode_intl.config import AlicodeIntlConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: AlicodeIntlConfig = AlicodeIntlConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Alibaba Intl API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Alibaba Intl."""
    return await fetch_models_header_auth(_config, api_key)
