"""Hugging Face model fetching — uses shared helper."""

from app.providers.huggingface.config import HuggingfaceConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: HuggingfaceConfig = HuggingfaceConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Hugging Face API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Hugging Face."""
    return await fetch_models_header_auth(_config, api_key)
