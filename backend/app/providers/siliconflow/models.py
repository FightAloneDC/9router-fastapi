"""SiliconFlow model fetching — uses shared helper."""

from app.providers.siliconflow.config import SiliconflowConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: SiliconflowConfig = SiliconflowConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from SiliconFlow API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from SiliconFlow."""
    return await fetch_models_header_auth(_config, api_key)
