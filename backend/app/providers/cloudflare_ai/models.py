"""Cloudflare AI model fetching — uses account_id from providerSpecificData."""

import httpx

from app.providers.cloudflare_ai.config import CloudflareAiConfig

_config: CloudflareAiConfig = CloudflareAiConfig()
TIMEOUT: float = 15.0


def parse_response(data: dict) -> list[dict]:
    """Cloudflare returns {result: [...]}."""
    return data.get("result", data.get("data", []))


async def fetch_models(api_key: str) -> list[dict]:
    """Cloudflare needs account_id in URL — handled at endpoint level."""
    return []
