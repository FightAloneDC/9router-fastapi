"""Provider credential validation functions."""

import json
from typing import Optional

import httpx

from app.schemas.provider import ProviderValidateResponse


async def _validate_openai_compatible(
    api_key: str, base_url: str, extra_headers: Optional[dict] = None
) -> ProviderValidateResponse:
    """Validate credentials for OpenAI-compatible providers by calling GET /models."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="No API key configured for this connection")
    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 401:
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code == 403:
                return ProviderValidateResponse(valid=False, error="API key forbidden (access denied)")
            if resp.status_code >= 400:
                error_text = resp.text[:200]
                return ProviderValidateResponse(valid=False, error=f"Provider returned {resp.status_code}: {error_text}")
            data = resp.json()
            models = []
            if isinstance(data, dict) and "data" in data:
                models = [m.get("id", "") for m in data["data"] if m.get("id")]
            return ProviderValidateResponse(valid=True, models=models or None)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error=f"Cannot connect to {base_url}")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_anthropic(api_key: str, base_url: Optional[str] = None) -> ProviderValidateResponse:
    """Validate Anthropic credentials."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="No API key configured for this connection")
    if base_url:
        url = base_url.rstrip("/")
        if url.endswith("/messages"):
            url = url[:-9]
        url = f"{url}/models"
    else:
        url = "https://api.anthropic.com/v1/models"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 500:
                return ProviderValidateResponse(valid=False, error=f"Server error ({resp.status_code})")
            return ProviderValidateResponse(valid=True)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to provider")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_google(api_key: str) -> ProviderValidateResponse:
    """Validate Google/Gemini credentials by listing models."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"Google returned {resp.status_code}")
            data = resp.json()
            models = []
            if isinstance(data, dict) and "models" in data:
                models = [m.get("name", "").replace("models/", "") for m in data["models"] if m.get("name")]
            return ProviderValidateResponse(valid=True, models=models or None)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to Google API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_azure(api_key: str, extra_data: dict) -> ProviderValidateResponse:
    """Validate Azure OpenAI credentials."""
    endpoint = (extra_data.get("azureEndpoint") or extra_data.get("endpoint") or "").rstrip("/")
    deployment = extra_data.get("deployment") or ""
    api_version = extra_data.get("apiVersion") or "2024-02-15-preview"
    if not endpoint:
        return ProviderValidateResponse(valid=False, error="Azure endpoint URL is required")
    if not deployment:
        return ProviderValidateResponse(valid=False, error="Azure deployment name is required")
    url = f"{endpoint}/openai/deployments?api-version={api_version}"
    headers = {"api-key": api_key}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"Azure returned {resp.status_code}")
            return ProviderValidateResponse(valid=True)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error=f"Cannot connect to {endpoint}")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_cloudflare(api_key: str, extra_data: dict) -> ProviderValidateResponse:
    """Validate Cloudflare AI credentials using accountId."""
    account_id = extra_data.get("accountId", "")
    if not account_id:
        return ProviderValidateResponse(valid=False, error="Cloudflare Account ID is required")
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for Cloudflare AI")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "@cf/meta/llama-3-8b-instruct", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key or Account ID (unauthorized)")
            if resp.status_code >= 400:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                errors = data.get("errors", [])
                msg = errors[0].get("message", f"Cloudflare returned {resp.status_code}") if errors else f"Cloudflare returned {resp.status_code}"
                return ProviderValidateResponse(valid=False, error=msg)
            return ProviderValidateResponse(valid=True)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to Cloudflare API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_openai_chat(api_key: str, base_url: str) -> ProviderValidateResponse:
    """Validate Kilo Gateway credentials by listing available models."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for Kilo Gateway")
    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = data.get("error", {}).get("message", f"Kilo Gateway returned {resp.status_code}") if isinstance(data.get("error"), dict) else f"Kilo Gateway returned {resp.status_code}"
                return ProviderValidateResponse(valid=False, error=error_msg)
            data = resp.json()
            models = data.get("data", [])
            model_ids = [m.get("id") for m in models if isinstance(m, dict)]
            return ProviderValidateResponse(valid=True, models=model_ids)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to Kilo Gateway API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_ollama(base_url: str) -> ProviderValidateResponse:
    """Validate Ollama by listing tags."""
    url = f"{base_url}/api/tags"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"Ollama returned {resp.status_code}")
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            return ProviderValidateResponse(valid=True, models=models or None)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error=f"Cannot connect to Ollama at {base_url}. Is it running?")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_vertex(api_key: str) -> ProviderValidateResponse:
    """Validate Vertex AI credentials."""
    # Service account JSON
    try:
        parsed = json.loads(api_key)
        if isinstance(parsed, dict) and parsed.get("type") == "service_account":
            valid = bool(parsed.get("client_email") and parsed.get("private_key") and parsed.get("project_id"))
            return ProviderValidateResponse(valid=valid, error=None if valid else "Invalid service account JSON")
    except (json.JSONDecodeError, TypeError):
        pass

    # Raw API key: probe Vertex
    url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/__probe__:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, headers={"Content-Type": "application/json"}, json={})
            valid = resp.status_code not in (401, 403)
            return ProviderValidateResponse(valid=valid, error=None if valid else "Invalid API key")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


# ── Media provider validators (TTS / STT / embedding) ──────────────────


def _validate_noauth() -> ProviderValidateResponse:
    """Providers that require no credentials (edge-tts, local-device)."""
    return ProviderValidateResponse(valid=True, models=None)


async def _validate_elevenlabs(api_key: str) -> ProviderValidateResponse:
    """Validate ElevenLabs credentials by listing voices."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for ElevenLabs")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
            )
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"ElevenLabs returned {resp.status_code}: {resp.text[:200]}")
            voices = resp.json().get("voices", [])
            return ProviderValidateResponse(valid=True, models=[v.get("voice_id", "") for v in voices if v.get("voice_id")] or None)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to ElevenLabs API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_deepgram(api_key: str) -> ProviderValidateResponse:
    """Validate Deepgram credentials by listing models."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for Deepgram")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                "https://api.deepgram.com/v1/models",
                headers={"Authorization": f"Token {api_key}"},
            )
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"Deepgram returned {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            tts_models = [m.get("canonical_name") or m.get("name", "") for m in data.get("tts", []) if m.get("name")]
            stt_models = [m.get("canonical_name") or m.get("name", "") for m in data.get("stt", []) if m.get("name")]
            all_models = tts_models + stt_models
            return ProviderValidateResponse(valid=True, models=all_models or None)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to Deepgram API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_inworld(api_key: str) -> ProviderValidateResponse:
    """Validate Inworld credentials by listing TTS voices (uses Basic auth)."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for Inworld")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                "https://api.inworld.ai/tts/v1/voices",
                headers={"Authorization": f"Basic {api_key}"},
            )
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"Inworld returned {resp.status_code}: {resp.text[:200]}")
            voices = resp.json().get("voices", [])
            return ProviderValidateResponse(valid=True, models=[v.get("voiceId", "") for v in voices if v.get("voiceId")] or None)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to Inworld API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_voyage(api_key: str) -> ProviderValidateResponse:
    """Validate Voyage AI credentials with a minimal embedding call."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for Voyage AI")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"input": "ping", "model": "voyage-3"},
            )
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            # 400 here likely means model not available — treat as auth-OK
            if resp.status_code >= 500:
                return ProviderValidateResponse(valid=False, error=f"Voyage returned {resp.status_code}")
            return ProviderValidateResponse(valid=True)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to Voyage AI API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_assemblyai(api_key: str) -> ProviderValidateResponse:
    """Validate AssemblyAI credentials via account endpoint."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for AssemblyAI")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # AssemblyAI uses raw API key in Authorization header (no Bearer prefix)
            resp = await client.get(
                "https://api.assemblyai.com/v2/transcript?limit=1",
                headers={"Authorization": api_key},
            )
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"AssemblyAI returned {resp.status_code}: {resp.text[:200]}")
            return ProviderValidateResponse(valid=True)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to AssemblyAI API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])


async def _validate_minimax(api_key: str, region: str = "minimax") -> ProviderValidateResponse:
    """Validate MiniMax credentials via get_voice endpoint."""
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required for MiniMax")
    endpoints = {
        "minimax": "https://api.minimax.io/v1/get_voice",
        "minimax-cn": "https://api.minimaxi.com/v1/get_voice",
    }
    url = endpoints.get(region, endpoints["minimax"])
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"voice_type": "all"},
            )
            if resp.status_code in (401, 403):
                return ProviderValidateResponse(valid=False, error="Invalid API key (unauthorized)")
            if resp.status_code >= 400:
                return ProviderValidateResponse(valid=False, error=f"MiniMax returned {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            base_resp = data.get("base_resp") or data.get("baseResp", {})
            status_code = base_resp.get("status_code") or base_resp.get("statusCode", 0)
            if status_code != 0:
                return ProviderValidateResponse(valid=False, error=base_resp.get("status_msg") or base_resp.get("statusMsg", "MiniMax error"))
            voices = data.get("system_voice", []) or []
            voice_ids = [v.get("voice_id") or v.get("voiceId", "") for v in voices if v.get("voice_id") or v.get("voiceId")]
            return ProviderValidateResponse(valid=True, models=voice_ids or None)
        except httpx.ConnectError:
            return ProviderValidateResponse(valid=False, error="Cannot connect to MiniMax API")
        except httpx.TimeoutException:
            return ProviderValidateResponse(valid=False, error="Connection timed out")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e)[:200])
