"""NVIDIA NIM model fetching — uses shared helper."""

from app.providers.nvidia.config import NvidiaConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: NvidiaConfig = NvidiaConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from NVIDIA NIM API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from NVIDIA NIM."""
    return await fetch_models_header_auth(_config, api_key)
