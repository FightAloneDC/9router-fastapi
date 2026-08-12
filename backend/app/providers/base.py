"""Base provider configuration — shared defaults for all providers.

Child classes override identity fields (PROVIDER_NAME, PROVIDER_ID, ALIAS,
BASE_URL, SERVICE_KINDS) and inherit connection/auth defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pydantic import BaseModel

from app.services.outbound_proxy import create_upstream_client


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

    # ── UI Metadata (served via /providers/catalog) ────────────────────
    DEPRECATED: bool = False
    DEPRECATION_NOTICE: str = ""
    HIDDEN: bool = False
    NO_AUTH: bool = False
    PASSTHROUGH_MODELS: bool = False
    REGIONS: list[dict] | None = None
    DEFAULT_REGION: str = ""
    THINKING_CONFIG: dict | None = None
    MEDIA_PRIORITY: int = 100
    MODELS_FETCHER: dict | None = None
    SUPPORTS_PAT: bool = False
    SUPPORTS_BULK_IMPORT: bool = False
    # Bulk import payload shape: "farm-json" (array of accounts
    # with email + tokens) or "api-keys" (one key per line,
    # optionally "key|name").
    BULK_IMPORT_FORMAT: str = "farm-json"
    REQUIRES_PROXY: bool = False
    CUSTOM_MODAL: str = ""  # frontend modal component name (e.g. "kiro", "cursor", "gitlab")
    PROVIDER_SPECIFIC_DATA: bool = False  # needs extra form fields in AddKeyModal
    CATEGORY: str = ""  # "free", "freeTier", "webCookie" (empty = derive from auth)

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class BaseMetadata(BaseModel):
    """UI display metadata for a provider."""

    name: str
    color: str
    textIcon: str
    icon: str = "Box"
    website: str = ""
    notice: dict | None = None
    authHint: str = ""


@dataclass
class ValidateResult:
    """Standardized result from provider validation."""

    valid: bool
    error: str | None = None
    models: list[str] | None = None
    latency_ms: int = 0
    method: str | None = None
    dimensions: int | None = None


class BaseProviderHandler:
    """Base handler for provider-specific operations.

    Override methods in child class for provider-specific behavior.
    Default implementation uses OpenAI-compatible API.
    """

    def __init__(self, config: BaseProviderConfig) -> None:
        self.config = config

    async def prepare_request(
        self,
        headers: dict[str, str],
        body: dict,
        stream: bool = False,
    ) -> tuple[dict[str, str], dict]:
        """Async hook to modify headers/body before sending upstream request.

        Override for providers that need pre-request steps (e.g. JWT bootstrap).
        Called by the proxy after build_headers but before sending the request.

        Returns:
            (headers, body) — possibly modified.
        """
        return headers, body

    async def try_refresh_on_auth_error(
        self,
        db: object,
        connection_id: str,
    ) -> bool:
        """Refresh credentials after an auth-related upstream failure.

        Override in providers that support token refresh (e.g. OAuth).
        Returns True if credentials were refreshed and the caller should
        retry the request.
        """
        return False

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
        self, api_key: str, base_url: str, data: dict | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> ValidateResult:
        """Default validation: GET /models with Bearer auth."""
        import time
        import httpx

        start = time.monotonic()
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        if self.config.EXTRA_HEADERS:
            headers.update(self.config.EXTRA_HEADERS)
        if extra_headers:
            headers.update(extra_headers)

        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 401:
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code == 403:
                    return ValidateResult(valid=False, error="API key forbidden", latency_ms=latency)
                if resp.status_code >= 400:
                    error_msg = f"HTTP {resp.status_code}"
                    try:
                        error_data = resp.json()
                        if isinstance(error_data, dict) and "error" in error_data:
                            err = error_data["error"]
                            if isinstance(err, dict) and "message" in err:
                                error_msg = err["message"]
                            elif isinstance(err, str):
                                error_msg = err
                    except Exception:
                        pass
                    return ValidateResult(valid=False, error=error_msg, latency_ms=latency)
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

    async def _validate_anthropic_compatible(
        self, api_key: str, base_url: str
    ) -> ValidateResult:
        """Anthropic-compatible validation: GET /models with x-api-key + anthropic-version."""
        import time
        import httpx

        start = time.monotonic()
        url = f"{base_url}/models"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Authorization": f"Bearer {api_key}",
        }

        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 500:
                    return ValidateResult(valid=False, error=f"Server error ({resp.status_code})", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to provider", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def _validate_embedding(
        self, api_key: str, base_url: str, model_id: str
    ) -> ValidateResult:
        """Embedding validation: POST /embeddings with model + input."""
        import time
        import httpx

        start = time.monotonic()
        url = f"{base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.post(
                    url, headers=headers,
                    json={"model": model_id, "input": "ping"},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.is_success:
                    dims = None
                    try:
                        data = resp.json()
                        emb = data.get("data", [{}])
                        if emb and isinstance(emb[0].get("embedding"), list):
                            dims = len(emb[0]["embedding"])
                    except Exception:
                        pass
                    return ValidateResult(valid=True, method="embeddings", dimensions=dims, latency_ms=latency)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="API key unauthorized", latency_ms=latency)
                return ValidateResult(
                    valid=False, error=f"Embeddings request failed ({resp.status_code})",
                    method="embeddings", latency_ms=latency,
                )
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Connection refused", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Request timeout", latency_ms=int((time.monotonic() - start) * 1000))
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

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Build the full upstream URL for chat/completions requests.

        Override in child class for provider-specific URL formats.
        Default: OpenAI-compatible /chat/completions
        """
        return f"{base_url.rstrip('/')}/chat/completions"

    def build_headers(self, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
        """Build HTTP headers for upstream request.

        Override in child class for provider-specific auth (e.g. Qoder COSY).
        Default: standard auth header from config.
        """
        if not api_key:
            raise ValueError(f"No API key configured for provider \"{self.config.PROVIDER_ID}\"")

        headers = {"Content-Type": "application/json"}
        headers[self.config.AUTH_HEADER] = f"{self.config.AUTH_PREFIX}{api_key}"
        if self.config.EXTRA_HEADERS:
            headers.update(self.config.EXTRA_HEADERS)
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def build_embeddings_url(self, chat_url: str) -> str:
        """Transform chat/completions URL to embeddings URL.

        Override in child class for provider-specific embeddings endpoints.
        Default: /chat/completions → /embeddings
        """
        if chat_url.endswith("/chat/completions"):
            return chat_url[:-len("/chat/completions")] + "/embeddings"
        if "/chat/completions" in chat_url:
            return chat_url.replace("/chat/completions", "/embeddings")
        return chat_url.rstrip("/") + "/embeddings"

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Transform embeddings request body for provider-specific formats.

        Override in child class for non-OpenAI formats (e.g. Gemini).
        Default: pass through with model override.
        """
        return {**body, "model": model}

    def unwrap_response(self, response_text: str) -> dict:
        """Unwrap provider-specific response envelope.

        Override in child class for providers with custom envelopes (e.g. Qoder).
        Default: standard JSON parse.
        """
        import json
        return json.loads(response_text)
