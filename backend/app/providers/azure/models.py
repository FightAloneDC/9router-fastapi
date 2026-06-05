"""Azure OpenAI model fetching — custom (resource-based URL)."""

import httpx

from app.providers.azure.config import AzureConfig

_config: AzureConfig = AzureConfig()
TIMEOUT: float = 15.0


def parse_response(data: dict) -> list[dict]:
    """Azure returns standard OpenAI format."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Azure model fetching needs resource name — handled at endpoint level."""
    return []
