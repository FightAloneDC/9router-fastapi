"""Gemini provider handler — query param auth (?key=)."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class GeminiHandler(BaseProviderHandler):
    """Handler for Gemini/Google provider (query param auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        start = time.monotonic()
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Google returned {resp.status_code}", latency_ms=latency)
                data_resp = resp.json()
                models = []
                if isinstance(data_resp, dict) and "models" in data_resp:
                    models = [m.get("name", "").replace("models/", "") for m in data_resp["models"] if m.get("name")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Google API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        from app.providers.model_helpers import fetch_models_query_auth
        from app.providers.base import BaseProviderConfig

        if not api_key:
            raise ValueError("No API key configured")

        config = BaseProviderConfig(
            PROVIDER_NAME="Gemini",
            PROVIDER_ID="gemini",
            ALIAS="gemini",
            BASE_URL="https://generativelanguage.googleapis.com/v1beta",
            AUTH_QUERY_PARAM="key",
        )
        models_raw = await fetch_models_query_auth(config, api_key)

        normalized = []
        for m in models_raw:
            name = m.get("name", "").replace("models/", "")
            if name:
                normalized.append({"id": name, "name": name})
        return [self._normalize_model(m) for m in normalized if self._normalize_model(m).get("id")]

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Gemini uses /models/{model}:generateContent format."""
        base = base_url.rstrip("/")
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        model_id = model.replace("models/", "") if model else ""
        if model_id:
            return f"{base}/models/{model_id}:{action}"
        return f"{base}/models"

    def build_embeddings_url(self, chat_url: str) -> str:
        """Gemini uses embedContent instead of /embeddings."""
        if ":generateContent" in chat_url:
            return chat_url.replace(":generateContent", ":embedContent")
        return super().build_embeddings_url(chat_url)

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Gemini uses content.parts format for embeddings."""
        input_text = body.get("input", "")
        if isinstance(input_text, list):
            input_text = " ".join(str(x) for x in input_text)
        return {
            "model": model,
            "content": {"parts": [{"text": str(input_text)}]},
        }
