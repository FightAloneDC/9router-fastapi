"""Image generation adapters for /v1/images/generations endpoint.

Each adapter takes a normalized set of args and returns a list of image entries
compatible with the OpenAI Images API response format:
  ``[{"url": "..."}]`` or ``[{"b64_json": "...", "revised_prompt": "..."}]``

The dispatch table at the bottom maps provider IDs to adapter functions.

Iterasi 1: OpenAI-compatible providers (openai, siliconflow, huggingface,
           replicate, recraft, runwayml, nanobanana, codex).
           Local/no-auth providers (sdwebui, comfyui).
Special:   fal-ai, stability-ai, bfl, gemini, minimax, cloudflare-ai → stubs.
"""

from __future__ import annotations

from typing import Any, Callable

import httpx


# ─────────────────────────────────────────────────────────────────────────────
# Group A: OpenAI-compatible adapters
# ─────────────────────────────────────────────────────────────────────────────


async def image_openai_compatible(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    n: int,
    size: str,
    response_format: str,
    quality: str | None,
    style: str | None,
    extra_body: dict[str, Any] | None,
) -> list[dict]:
    """Generic OpenAI-compatible image generation.

    Works with: openai, siliconflow, huggingface, replicate, recraft,
    runwayml, nanobanana, codex, and any provider that follows the
    ``POST /images/generations`` convention.
    """
    url = f"{base_url.rstrip('/')}/images/generations"
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "response_format": response_format,
    }
    if quality:
        body["quality"] = quality
    if style:
        body["style"] = style
    if extra_body:
        body.update(extra_body)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    images = data.get("data", [])
    return [
        {
            "url": img.get("url"),
            "b64_json": img.get("b64_json"),
            "revised_prompt": img.get("revised_prompt"),
        }
        for img in images
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Group B: Local / no-auth adapters
# ─────────────────────────────────────────────────────────────────────────────


async def image_sdwebui(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    n: int,
    size: str,
    response_format: str,
    quality: str | None,
    style: str | None,
    extra_body: dict[str, Any] | None,
) -> list[dict]:
    """Stable Diffusion WebUI (AUTOMATIC1111) txt2img adapter.

    Endpoint: POST /sdapi/v1/txt2img
    Returns base64 images (SD WebUI doesn't support URL output).
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

    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    images_b64 = data.get("images", [])
    return [{"b64_json": b64, "url": None} for b64 in images_b64[:n]]


async def image_comfyui(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    n: int,
    size: str,
    response_format: str,
    quality: str | None,
    style: str | None,
    extra_body: dict[str, Any] | None,
) -> list[dict]:
    """ComfyUI adapter — stub.

    ComfyUI uses a complex workflow JSON system that requires specific
    workflow definitions per model. This stub returns 501 until a
    generic workflow builder is implemented.
    """
    raise NotImplementedError(
        "ComfyUI image generation requires a workflow definition. "
        "Use the ComfyUI web interface directly or provide a workflow JSON."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group C: Provider-specific adapters (stubs / TODO)
# ─────────────────────────────────────────────────────────────────────────────


async def _stub_adapter(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    n: int,
    size: str,
    response_format: str,
    quality: str | None,
    style: str | None,
    extra_body: dict[str, Any] | None,
) -> list[dict]:
    raise NotImplementedError("This provider's image adapter is not yet implemented.")


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch table
# ─────────────────────────────────────────────────────────────────────────────

IMAGE_ADAPTERS: dict[str, Callable[..., Any]] = {
    # OpenAI-compatible
    "openai": image_openai_compatible,
    "siliconflow": image_openai_compatible,
    "huggingface": image_openai_compatible,
    "replicate": image_openai_compatible,
    "recraft": image_openai_compatible,
    "runwayml": image_openai_compatible,
    "nanobanana": image_openai_compatible,
    "codex": image_openai_compatible,
    # Local / no-auth
    "sdwebui": image_sdwebui,
    "comfyui": image_comfyui,
    # Provider-specific (stubs)
    "fal-ai": _stub_adapter,
    "stability-ai": _stub_adapter,
    "bfl": _stub_adapter,
    "gemini": _stub_adapter,
    "minimax": _stub_adapter,
    "cloudflare-ai": _stub_adapter,
    "azure": _stub_adapter,
}
