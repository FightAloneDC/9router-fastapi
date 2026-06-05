"""Crawl4AI model fetching — no standard API listing."""

from app.providers.crawl4ai.config import Crawl4aiConfig

_config: Crawl4aiConfig = Crawl4aiConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """Crawl4AI does not expose a standard model listing endpoint."""
    return []
