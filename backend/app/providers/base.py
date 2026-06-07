"""Base provider configuration — shared defaults for all providers.

Child classes override identity fields (PROVIDER_NAME, PROVIDER_ID, ALIAS,
BASE_URL, SERVICE_KINDS) and inherit connection/auth defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pydantic import BaseModel


class BaseProviderConfig(BaseModel):
    """Base config for all providers.

    Covers header-based auth (default Bearer) and query-param auth (Gemini).
    Runtime data (API keys, custom baseUrl) come from ProviderConnection.data
    in the database — not from this config.
    """

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str
    PROVIDER_ID: str
    ALIAS: str
    BASE_URL: str

    # ── Connection defaults ─────────────────────────────────────────────
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = []

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}
    AUTH_QUERY_PARAM: str = ""  # non-empty for query-param auth (e.g. Gemini: "key")

    # ── Model type overrides ────────────────────────────────────────────
    # Maps model_id → type (e.g. "whisper-1" → "stt")
    # Used by infer_model_type() to override regex-based heuristics
    MODEL_TYPE_OVERRIDES: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class BaseMetadata(BaseModel):
    """UI display metadata for a provider."""

    name: str
    color: str
    textIcon: str


@dataclass
class ValidateResult:
    """Standardized result from provider validation."""

    valid: bool
    error: str | None = None
    models: list[str] | None = None
    latency_ms: int = 0


class BaseProviderHandler:
    """Base handler for provider-specific operations.

    Override methods in child class for provider-specific behavior.
    Default implementation uses OpenAI-compatible API.
    """

    def __init__(self, config: BaseProviderConfig) -> None:
        self.config = config

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        """Validate provider credentials."""
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")
        base_url = self._resolve_base_url(data)
        if not base_url:
            return ValidateResult(valid=False, error="Base URL is required")
        return await self._validate_openai_compatible(api_key, base_url, data)

    async def test_connection(self, api_key: str, data: dict | None = None) -> ValidateResult:
        """Test provider connection. Same as validate by default."""
        return await self.validate(api_key, data)

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        """Fetch available models from provider."""
        from app.providers.model_helpers import fetch_models_header_auth

        if not api_key:
            raise ValueError("No API key configured")

        config = self._build_fetch_config(data)
        models_raw = await fetch_models_header_auth(config, api_key)
        return [self._normalize_model(m) for m in models_raw if self._normalize_model(m).get("id")]

    def resolve_base_url(self, data: dict | None = None) -> str:
        """Resolve effective base URL from config + connection data."""
        return self._resolve_base_url(data)

    def _resolve_base_url(self, data: dict | None = None) -> str:
        """Internal: resolve base URL."""
        if data and data.get("baseUrl"):
            return data["baseUrl"].rstrip("/")
        return self.config.BASE_URL.rstrip("/") if self.config.BASE_URL else ""

    def _build_fetch_config(self, data: dict | None = None) -> BaseProviderConfig:
        """Build config for model fetching."""
        return BaseProviderConfig(
            PROVIDER_NAME=self.config.PROVIDER_NAME,
            PROVIDER_ID=self.config.PROVIDER_ID,
            ALIAS=self.config.ALIAS,
            BASE_URL=self._resolve_base_url(data),
            AUTH_HEADER=self.config.AUTH_HEADER,
            AUTH_PREFIX=self.config.AUTH_PREFIX,
            EXTRA_HEADERS=self.config.EXTRA_HEADERS,
        )

    async def _validate_openai_compatible(
        self, api_key: str, base_url: str, data: dict | None = None
    ) -> ValidateResult:
        """Default validation: GET /models with Bearer auth."""
        import time
        import httpx

        start = time.monotonic()
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        if self.config.EXTRA_HEADERS:
            headers.update(self.config.EXTRA_HEADERS)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 401:
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code == 403:
                    return ValidateResult(valid=False, error="API key forbidden", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"HTTP {resp.status_code}", latency_ms=latency)
                data_resp = resp.json()
                models = []
                if isinstance(data_resp, dict) and "data" in data_resp:
                    models = [m.get("id", "") for m in data_resp["data"] if m.get("id")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error=f"Cannot connect to {base_url}", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    def _normalize_model(self, m) -> dict:
        """Normalize a model entry to {id, name, type}."""
        from app.routers.providers.constants import infer_model_type, _get_model_type_overrides

        if isinstance(m, str):
            return {"id": m, "name": m, "type": infer_model_type(m)}
        model_id = m.get("id") or m.get("name") or m.get("model", "")
        name = m.get("name") or m.get("display_name") or m.get("displayName") or m.get("id", "")
        model_type = m.get("type") or _get_model_type_overrides().get(model_id) or infer_model_type(model_id)
        return {"id": model_id, "name": name, "type": model_type}
