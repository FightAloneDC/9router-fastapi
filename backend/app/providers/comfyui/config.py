"""ComfyUI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class ComfyuiConfig(BaseModel):
    """ComfyUI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "ComfyUI"
    PROVIDER_ID: str = "comfyui"
    ALIAS: str = "cfui"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "http://localhost:8188"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class ComfyuiMetadata(BaseModel):
    """ComfyUI UI display metadata."""

    name: str = "ComfyUI"
    color: str = "#EC4899"
    textIcon: str = "CU"
