"""Alibaba Studio model fetching — uses shared helper."""

from app.providers.alims_intl.config import AlimsIntlConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: AlimsIntlConfig = AlimsIntlConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Alibaba Studio API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Alibaba Studio."""
    return await fetch_models_header_auth(_config, api_key)
