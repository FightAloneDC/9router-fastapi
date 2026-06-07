"""Stable Diffusion WebUI handler — image generation via AUTOMATIC1111 API."""

from __future__ import annotations

from typing import Any

from app.providers.base import BaseProviderConfig, BaseProviderHandler


class SdwebuiHandler(BaseProviderHandler):
    """Handler for Stable Diffusion WebUI (AUTOMATIC1111) image generation.

    Endpoint: POST /sdapi/v1/txt2img
    Auth: none (local service)
    Response: {"images": ["<base64>", ...]}
    """

    def __init__(self) -> None:
        config = BaseProviderConfig(
            PROVIDER_NAME="Stable Diffusion WebUI",
            PROVIDER_ID="sdwebui",
            ALIAS="sd",
            BASE_URL="http://localhost:7860",
            SERVICE_KINDS=["image"],
        )
        super().__init__(config)

    def build_image_request(
        self,
        base_url: str,
        model: str,
        prompt: str,
        n: int,
        size: str,
        response_format: str,
        quality: str | None,
        style: str | None,
        extra_body: dict[str, Any] | None,
    ) -> tuple[str, str, dict[str, str], dict[str, Any]]:
        """Build SD WebUI txt2img request.

        Returns:
            (url, method, headers, body) tuple
        """
        url = f"{base_url.rstrip('/')}/sdapi/v1/txt2img"

        width, height = (int(x) for x in size.split("x")) if "x" in size else (512, 512)

        body: dict[str, Any] = {
            "prompt": prompt,
            "batch_size": n,
            "width": width,
            "height": height,
        }
        if extra_body:
            body.update(extra_body)

        headers = {"Content-Type": "application/json"}
        return url, "POST", headers, body

    def parse_image_response(self, data: dict) -> list[dict]:
        """Parse SD WebUI response into OpenAI-compatible image entries.

        SD WebUI returns {"images": ["<base64>", ...]}.
        OpenAI format expects [{"b64_json": "...", "url": null}].
        """
        images_b64 = data.get("images", [])
        return [{"b64_json": b64, "url": None} for b64 in images_b64]
