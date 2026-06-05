"""SearXNG model fetching — no standard API listing."""

from app.providers.searxng.config import SearxngConfig

_config: SearxngConfig = SearxngConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """SearXNG does not expose a standard model listing endpoint."""
    return []
