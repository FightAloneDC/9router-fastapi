"""SD WebUI model fetching — local instance, no standard listing."""

from app.providers.sdwebui.config import SdwebuiConfig

_config: SdwebuiConfig = SdwebuiConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """SD WebUI does not expose a standard model listing endpoint."""
    return []
