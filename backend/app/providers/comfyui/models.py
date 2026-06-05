"""ComfyUI model fetching — local instance, no standard listing."""

from app.providers.comfyui.config import ComfyuiConfig

_config: ComfyuiConfig = ComfyuiConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """ComfyUI does not expose a standard model listing endpoint."""
    return []
