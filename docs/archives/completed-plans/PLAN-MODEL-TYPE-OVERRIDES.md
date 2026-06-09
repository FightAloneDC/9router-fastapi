# Model Type Overrides — Distribusi ke Provider Config

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pindahkan `MODEL_TYPE_OVERRIDES` dari `backend/app/routers/providers/constants.py` ke masing-masing provider config, sehingga setiap provider mendefinisikan model type overrides-nya sendiri.

**Architecture:** Tambahkan field `MODEL_TYPE_OVERRIDES: dict[str, str]` ke `BaseProviderConfig`. Setiap provider mengisi field ini di config-nya. Buat aggregator di `providers/__init__.py` yang menggabungkan semua overrides menjadi satu dict global. Update consumer code untuk menggunakan aggregator.

**Tech Stack:** Python, Pydantic, FastAPI

---

## Problem

`MODEL_TYPE_OVERRIDES` saat ini berisi ~60 entry yang didefinisikan secara terpusat di `backend/app/routers/providers/constants.py`. 

**Masalah:**
- Jika provider menambah/mengubah model, harus edit file constants.py (bukan file provider)
- Tidak ada ownership yang jelas — siapa yang punya model "whisper-1"? OpenAI? Deepgram?
- Sulit maintain ketika ada 78+ provider

**Solusi:** Distribusikan ke masing-masing provider config. Setiap provider tahu model apa saja yang dia punya dan tipe-nya.

---

## File Structure

### Files Modified

| File | Change |
|------|--------|
| `backend/app/providers/base.py` | Add `MODEL_TYPE_OVERRIDES` field |
| `backend/app/providers/__init__.py` | Add aggregator function `get_all_model_type_overrides()` |
| `backend/app/providers/openai/config.py` | Add OpenAI model overrides |
| `backend/app/providers/mistral/config.py` | Add Mistral model overrides |
| `backend/app/providers/nvidia/config.py` | Add Nvidia model overrides |
| `backend/app/providers/voyage_ai/config.py` | Add Voyage AI model overrides |
| `backend/app/providers/jina_ai/config.py` | Add Jina AI model overrides |
| `backend/app/providers/together/config.py` | Add Together model overrides |
| `backend/app/providers/deepgram/config.py` | Add Deepgram model overrides |
| `backend/app/providers/elevenlabs/config.py` | Add ElevenLabs model overrides |
| `backend/app/providers/playht/config.py` | Add PlayHT model overrides |
| `backend/app/providers/minimax/config.py` | Add Minimax model overrides |
| `backend/app/providers/minimax_cn/config.py` | Add Minimax CN model overrides |
| `backend/app/providers/gemini/config.py` | Add Gemini model overrides |
| `backend/app/providers/coqui/config.py` | Add Coqui model overrides |
| `backend/app/providers/inworld/config.py` | Add Inworld model overrides |
| `backend/app/providers/tortoise/config.py` | Add Tortoise model overrides |
| `backend/app/providers/huggingface/config.py` | Add HuggingFace model overrides |
| `backend/app/providers/edge_tts/config.py` | Add Edge TTS model overrides |
| `backend/app/providers/local_device/config.py` | Add Local Device model overrides |
| `backend/app/providers/google_tts/config.py` | Add Google TTS model overrides |
| `backend/app/providers/cartesia/config.py` | Add Cartesia model overrides |
| `backend/app/routers/providers/constants.py` | Remove MODEL_TYPE_OVERRIDES, import from providers |
| `backend/app/routers/providers/helpers.py` | Update import |
| `backend/app/routers/providers/testing.py` | Update import |
| `backend/app/routers/v1_proxy/models.py` | Update import |

### Files NOT Modified

| File | Reason |
|------|--------|
| `backend/app/providers/<other>/config.py` | No model overrides needed |

---

## Model Ownership Mapping

Mapping model ID ke provider berdasarkan naming convention:

| Provider | Models |
|----------|--------|
| **openai** | text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002, whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe, tts-1, tts-1-hd, gpt-4o-mini-tts, dall-e-3, dall-e-2 |
| **mistral** | mistral-embed |
| **nvidia** | nvidia/nv-embedqa-e5-v5, Qwen/Qwen3-Embedding-8B |
| **voyage_ai** | voyage-3-large, voyage-3.5, voyage-3.5-lite, voyage-code-3, voyage-finance-2, voyage-law-2, voyage-multilingual-2 |
| **jina_ai** | jina-embeddings-v3, jina-embeddings-v2-base-en, jina-embeddings-v2-base-code |
| **together** | togethercomputer/m2-bert-80M-8k-retrieval |
| **deepgram** | nova-3, nova-2, universal-3-pro, universal-2 |
| **elevenlabs** | eleven_multilingual_v2, eleven_turbo_v2_5, sonic-2, sonic-3 |
| **playht** | PlayDialog, Play3.0-mini |
| **minimax** | speech-2.8-hd, speech-2.8-turbo, speech-2.6-hd, speech-2.6-turbo, speech-02-hd, speech-02-turbo, speech-01-hd, speech-01-turbo |
| **gemini** | gemini-2.5-flash-preview-tts, gemini-2.5-pro-preview-tts, text-embedding-004, embedding-001 |
| **coqui** | melo-tts |
| **inworld** | inworld-tts-1.5-mini, inworld-tts-1.5-max |
| **tortoise** | tortoise-v2, facebook/mms-tts-eng, microsoft/speecht5_tts |
| **huggingface** | openai/whisper-large-v3, openai/whisper-small |
| **cartesia** | (no overrides in current list) |
| **edge_tts** | (no overrides in current list) |
| **local_device** | (no overrides in current list) |
| **google_tts** | (no overrides in current list) |

---

## Tasks

### Task 1: Add MODEL_TYPE_OVERRIDES field to BaseProviderConfig

**Files:**
- Modify: `backend/app/providers/base.py`

- [ ] **Step 1: Add field to BaseProviderConfig**

```python
class BaseProviderConfig(BaseModel):
    """Base config for all providers."""

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
    AUTH_QUERY_PARAM: str = ""

    # ── Model type overrides ────────────────────────────────────────────
    # Maps model_id → type (e.g. "whisper-1" → "stt")
    # Used by infer_model_type() to override regex-based heuristics
    MODEL_TYPE_OVERRIDES: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/base.py
git commit -m "feat(providers): add MODEL_TYPE_OVERRIDES field to BaseProviderConfig"
```

---

### Task 2: Add aggregator function to providers/__init__.py

**Files:**
- Modify: `backend/app/providers/__init__.py`

- [ ] **Step 1: Add get_all_model_type_overrides() function**

Add at the end of `__init__.py`:

```python
# ── Model type overrides aggregator ──────────────────────────────────────
def get_all_model_type_overrides() -> dict[str, str]:
    """Aggregate MODEL_TYPE_OVERRIDES from all providers.

    Each provider can define MODEL_TYPE_OVERRIDES in its config to map
    model_id → type (e.g. "whisper-1" → "stt"). This function collects
    all overrides into a single dict.
    """
    from app.providers.provider import Provider

    overrides: dict[str, str] = {}
    for name in AVAILABLE_PROVIDERS:
        try:
            p = Provider(name)
            config = p.config()
            if hasattr(config, "MODEL_TYPE_OVERRIDES") and config.MODEL_TYPE_OVERRIDES:
                overrides.update(config.MODEL_TYPE_OVERRIDES)
        except (ValueError, ModuleNotFoundError):
            pass
    return overrides
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/__init__.py
git commit -m "feat(providers): add get_all_model_type_overrides aggregator"
```

---

### Task 3: Add overrides to OpenAI config

**Files:**
- Modify: `backend/app/providers/openai/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to OpenaiConfig**

```python
class OpenaiConfig(BaseProviderConfig):
    """OpenAI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenAI"
    PROVIDER_ID: str = "openai"
    ALIAS: str = "openai"
    BASE_URL: str = "https://api.openai.com/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "tts", "stt", "image", "imageToText", "webSearch"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "text-embedding-3-small": "embedding",
        "text-embedding-3-large": "embedding",
        "text-embedding-ada-002": "embedding",
        "whisper-1": "stt",
        "gpt-4o-transcribe": "stt",
        "gpt-4o-mini-transcribe": "stt",
        "tts-1": "tts",
        "tts-1-hd": "tts",
        "gpt-4o-mini-tts": "tts",
        "dall-e-3": "image",
        "dall-e-2": "image",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/openai/config.py
git commit -m "feat(openai): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 4: Add overrides to Mistral config

**Files:**
- Modify: `backend/app/providers/mistral/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to MistralConfig**

```python
class MistralConfig(BaseProviderConfig):
    """Mistral provider configuration."""

    PROVIDER_NAME: str = "Mistral"
    PROVIDER_ID: str = "mistral"
    ALIAS: str = "mi"
    BASE_URL: str = "https://api.mistral.ai/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "mistral-embed": "embedding",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/mistral/config.py
git commit -m "feat(mistral): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 5: Add overrides to Nvidia config

**Files:**
- Modify: `backend/app/providers/nvidia/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to NvidiaConfig**

```python
class NvidiaConfig(BaseProviderConfig):
    """Nvidia provider configuration."""

    PROVIDER_NAME: str = "Nvidia"
    PROVIDER_ID: str = "nvidia"
    ALIAS: str = "nv"
    BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "nvidia/nv-embedqa-e5-v5": "embedding",
        "Qwen/Qwen3-Embedding-8B": "embedding",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/nvidia/config.py
git commit -m "feat(nvidia): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 6: Add overrides to Voyage AI config

**Files:**
- Modify: `backend/app/providers/voyage_ai/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to VoyageAiConfig**

```python
class VoyageAiConfig(BaseProviderConfig):
    """Voyage AI provider configuration."""

    PROVIDER_NAME: str = "Voyage AI"
    PROVIDER_ID: str = "voyage-ai"
    ALIAS: str = "voyage"
    BASE_URL: str = "https://api.voyageai.com/v1"
    SERVICE_KINDS: list[str] = ["embedding"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "voyage-3-large": "embedding",
        "voyage-3.5": "embedding",
        "voyage-3.5-lite": "embedding",
        "voyage-code-3": "embedding",
        "voyage-finance-2": "embedding",
        "voyage-law-2": "embedding",
        "voyage-multilingual-2": "embedding",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/voyage_ai/config.py
git commit -m "feat(voyage-ai): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 7: Add overrides to Jina AI config

**Files:**
- Modify: `backend/app/providers/jina_ai/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to JinaAiConfig**

```python
class JinaAiConfig(BaseProviderConfig):
    """Jina AI provider configuration."""

    PROVIDER_NAME: str = "Jina AI"
    PROVIDER_ID: str = "jina-ai"
    ALIAS: str = "jina"
    BASE_URL: str = "https://api.jina.ai/v1"
    SERVICE_KINDS: list[str] = ["embedding"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "jina-embeddings-v3": "embedding",
        "jina-embeddings-v2-base-en": "embedding",
        "jina-embeddings-v2-base-code": "embedding",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/jina_ai/config.py
git commit -m "feat(jina-ai): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 8: Add overrides to Together config

**Files:**
- Modify: `backend/app/providers/together/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to TogetherConfig**

```python
class TogetherConfig(BaseProviderConfig):
    """Together provider configuration."""

    PROVIDER_NAME: str = "Together"
    PROVIDER_ID: str = "together"
    ALIAS: str = "to"
    BASE_URL: str = "https://api.together.xyz/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "image"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "togethercomputer/m2-bert-80M-8k-retrieval": "embedding",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/together/config.py
git commit -m "feat(together): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 9: Add overrides to Deepgram config

**Files:**
- Modify: `backend/app/providers/deepgram/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to DeepgramConfig**

```python
class DeepgramConfig(BaseProviderConfig):
    """Deepgram provider configuration."""

    PROVIDER_NAME: str = "Deepgram"
    PROVIDER_ID: str = "deepgram"
    ALIAS: str = "dg"
    BASE_URL: str = "https://api.deepgram.com/v1"
    SERVICE_KINDS: list[str] = ["stt", "tts"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Token "

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "nova-3": "stt",
        "nova-2": "stt",
        "universal-3-pro": "stt",
        "universal-2": "stt",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/deepgram/config.py
git commit -m "feat(deepgram): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 10: Add overrides to ElevenLabs config

**Files:**
- Modify: `backend/app/providers/elevenlabs/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to ElevenlabsConfig**

```python
class ElevenlabsConfig(BaseProviderConfig):
    """ElevenLabs provider configuration."""

    PROVIDER_NAME: str = "ElevenLabs"
    PROVIDER_ID: str = "elevenlabs"
    ALIAS: str = "el"
    BASE_URL: str = "https://api.elevenlabs.io/v1"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = "xi-api-key"
    AUTH_PREFIX: str = ""

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "eleven_multilingual_v2": "tts",
        "eleven_turbo_v2_5": "tts",
        "sonic-2": "tts",
        "sonic-3": "tts",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/elevenlabs/config.py
git commit -m "feat(elevenlabs): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 11: Add overrides to PlayHT config

**Files:**
- Modify: `backend/app/providers/playht/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to PlayhtConfig**

```python
class PlayhtConfig(BaseProviderConfig):
    """PlayHT provider configuration."""

    PROVIDER_NAME: str = "PlayHT"
    PROVIDER_ID: str = "playht"
    ALIAS: str = "playht"
    BASE_URL: str = "https://api.play.ht/v2"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "PlayDialog": "tts",
        "Play3.0-mini": "tts",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/playht/config.py
git commit -m "feat(playht): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 12: Add overrides to Minimax config

**Files:**
- Modify: `backend/app/providers/minimax/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to MinimaxConfig**

```python
class MinimaxConfig(BaseProviderConfig):
    """Minimax provider configuration."""

    PROVIDER_NAME: str = "Minimax"
    PROVIDER_ID: str = "minimax"
    ALIAS: str = "mm"
    BASE_URL: str = "https://api.minimax.chat/v1"
    SERVICE_KINDS: list[str] = ["llm", "tts"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "speech-2.8-hd": "tts",
        "speech-2.8-turbo": "tts",
        "speech-2.6-hd": "tts",
        "speech-2.6-turbo": "tts",
        "speech-02-hd": "tts",
        "speech-02-turbo": "tts",
        "speech-01-hd": "tts",
        "speech-01-turbo": "tts",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/minimax/config.py
git commit -m "feat(minimax): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 13: Add overrides to Gemini config

**Files:**
- Modify: `backend/app/providers/gemini/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to GeminiConfig**

```python
class GeminiConfig(BaseProviderConfig):
    """Gemini provider configuration."""

    PROVIDER_NAME: str = "Gemini"
    PROVIDER_ID: str = "gemini"
    ALIAS: str = "gemini"
    BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "tts"]
    AUTH_QUERY_PARAM: str = "key"

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "gemini-2.5-flash-preview-tts": "tts",
        "gemini-2.5-pro-preview-tts": "tts",
        "text-embedding-004": "embedding",
        "embedding-001": "embedding",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/gemini/config.py
git commit -m "feat(gemini): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 14: Add overrides to Coqui config

**Files:**
- Modify: `backend/app/providers/coqui/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to CoquiConfig**

```python
class CoquiConfig(BaseProviderConfig):
    """Coqui provider configuration."""

    PROVIDER_NAME: str = "Coqui"
    PROVIDER_ID: str = "coqui"
    ALIAS: str = "coqui"
    BASE_URL: str = ""
    SERVICE_KINDS: list[str] = ["tts"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "melo-tts": "tts",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/coqui/config.py
git commit -m "feat(coqui): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 15: Add overrides to Inworld config

**Files:**
- Modify: `backend/app/providers/inworld/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to InworldConfig**

```python
class InworldConfig(BaseProviderConfig):
    """Inworld provider configuration."""

    PROVIDER_NAME: str = "Inworld"
    PROVIDER_ID: str = "inworld"
    ALIAS: str = "inworld"
    BASE_URL: str = ""
    SERVICE_KINDS: list[str] = ["tts"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "inworld-tts-1.5-mini": "tts",
        "inworld-tts-1.5-max": "tts",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/inworld/config.py
git commit -m "feat(inworld): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 16: Add overrides to Tortoise config

**Files:**
- Modify: `backend/app/providers/tortoise/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to TortoiseConfig**

```python
class TortoiseConfig(BaseProviderConfig):
    """Tortoise provider configuration."""

    PROVIDER_NAME: str = "Tortoise"
    PROVIDER_ID: str = "tortoise"
    ALIAS: str = "tortoise"
    BASE_URL: str = ""
    SERVICE_KINDS: list[str] = ["tts"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "tortoise-v2": "tts",
        "facebook/mms-tts-eng": "tts",
        "microsoft/speecht5_tts": "tts",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/tortoise/config.py
git commit -m "feat(tortoise): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 17: Add overrides to HuggingFace config

**Files:**
- Modify: `backend/app/providers/huggingface/config.py`

- [ ] **Step 1: Add MODEL_TYPE_OVERRIDES to HuggingfaceConfig**

```python
class HuggingfaceConfig(BaseProviderConfig):
    """HuggingFace provider configuration."""

    PROVIDER_NAME: str = "HuggingFace"
    PROVIDER_ID: str = "huggingface"
    ALIAS: str = "hf"
    BASE_URL: str = "https://api-inference.huggingface.co/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "stt"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "openai/whisper-large-v3": "stt",
        "openai/whisper-small": "stt",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/huggingface/config.py
git commit -m "feat(huggingface): add MODEL_TYPE_OVERRIDES to config"
```

---

### Task 18: Update constants.py to import from providers

**Files:**
- Modify: `backend/app/routers/providers/constants.py`

- [ ] **Step 1: Replace MODEL_TYPE_OVERRIDES with import**

```python
"""Provider defaults, internal keys, and filter definitions."""

import re
from app.providers import get_all_model_type_overrides

# Fields stored in the data JSON blob that are NOT provider-specific config
_DATA_INTERNAL_KEYS = {
    "apiKey", "accessToken", "refreshToken", "idToken",
    "models", "roundRobin", "baseUrl", "testStatus",
    "displayName", "globalPriority", "defaultModel",
    "lastError", "lastErrorAt", "errorCode",
    "expiresAt", "lastUsedAt", "consecutiveUseCount",
}

# Sensitive fields to strip from output
_SENSITIVE_KEYS = {"apiKey", "accessToken", "refreshToken", "idToken"}

# Filter definitions for suggested models
SUGGESTED_MODELS_FILTERS = {
    "openrouter-free": lambda models: sorted(
        [
            {"id": m.get("id"), "name": m.get("name"), "contextLength": m.get("context_length")}
            for m in models
            if m.get("pricing", {}).get("prompt") == "0"
            and m.get("pricing", {}).get("completion") == "0"
            and (m.get("context_length") or 0) >= 200000
        ],
        key=lambda x: -(x.get("contextLength") or 0),
    ),
    "opencode-free": lambda models: [
        {"id": m.get("id"), "name": m.get("id")}
        for m in models
        if m.get("id", "").endswith("-free")
    ],
    "kilo-gateway": lambda models: [
        {"id": m.get("id"), "name": m.get("name") or m.get("id")}
        for m in models
        if m.get("id")
    ],
}

# ── Model Type System ──────────────────────────────────────────────────

# Lazy-loaded aggregated overrides from all providers
_MODEL_TYPE_OVERRIDES_CACHE: dict[str, str] | None = None

def _get_model_type_overrides() -> dict[str, str]:
    """Get aggregated MODEL_TYPE_OVERRIDES from all providers (cached)."""
    global _MODEL_TYPE_OVERRIDES_CACHE
    if _MODEL_TYPE_OVERRIDES_CACHE is None:
        _MODEL_TYPE_OVERRIDES_CACHE = get_all_model_type_overrides()
    return _MODEL_TYPE_OVERRIDES_CACHE

# Keep backward-compatible reference
MODEL_TYPE_OVERRIDES = property(lambda self: _get_model_type_overrides())

def infer_model_type(model_id: str) -> str:
    """Infer model type from model ID using regex heuristics."""
    mid = model_id.lower()

    # Check overrides first
    overrides = _get_model_type_overrides()
    if model_id in overrides:
        return overrides[model_id]

    # Embedding models
    if re.search(r"embed|e5-|bge-|gte-|nomic|cohere-embed|voyage-", mid):
        return "embedding"

    # TTS models
    if re.search(r"tts|speech|audio|voice", mid):
        return "tts"

    # STT models
    if re.search(r"whisper|transcri|stt|asr", mid):
        return "stt"

    # Image models
    if re.search(r"image|imagen|dall-?e|flux|sdxl|sd-|stable-diffusion|midjourney", mid):
        return "image"

    # Default: LLM
    return "llm"

def normalize_models_list(models) -> list:
    """Normalize models list to always include type field (backward compat).

    Handles both old string format and new object format.
    """
    if not models:
        return []
    result = []
    for m in models:
        if isinstance(m, str):
            result.append({"id": m, "type": infer_model_type(m)})
        elif isinstance(m, dict):
            if "type" not in m:
                m["type"] = infer_model_type(m.get("id", ""))
            result.append(m)
    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/providers/constants.py
git commit -m "refactor(constants): import MODEL_TYPE_OVERRIDES from providers"
```

---

### Task 19: Update helpers.py import

**Files:**
- Modify: `backend/app/routers/providers/helpers.py`

- [ ] **Step 1: Update import statement**

Change line 12 from:
```python
from app.routers.providers.constants import _DATA_INTERNAL_KEYS, MODEL_TYPE_OVERRIDES, infer_model_type, normalize_models_list
```

To:
```python
from app.routers.providers.constants import _DATA_INTERNAL_KEYS, _get_model_type_overrides, infer_model_type, normalize_models_list
```

- [ ] **Step 2: Update usage in _normalize_model function**

Change line 213 from:
```python
model_type = m.get("type") or MODEL_TYPE_OVERRIDES.get(model_id) or infer_model_type(model_id)
```

To:
```python
model_type = m.get("type") or _get_model_type_overrides().get(model_id) or infer_model_type(model_id)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/providers/helpers.py
git commit -m "refactor(helpers): update MODEL_TYPE_OVERRIDES import"
```

---

### Task 20: Update v1_proxy/models.py import

**Files:**
- Modify: `backend/app/routers/v1_proxy/models.py`

- [ ] **Step 1: Update import statement**

Change line 16 from:
```python
from app.routers.providers.constants import MODEL_TYPE_OVERRIDES, infer_model_type
```

To:
```python
from app.routers.providers.constants import _get_model_type_overrides, infer_model_type
```

- [ ] **Step 2: Update usage (lines 95-96 and 187-188)**

Change from:
```python
elif model_id in MODEL_TYPE_OVERRIDES:
    model_type = MODEL_TYPE_OVERRIDES[model_id]
```

To:
```python
elif model_id in _get_model_type_overrides():
    model_type = _get_model_type_overrides()[model_id]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/v1_proxy/models.py
git commit -m "refactor(v1-proxy): update MODEL_TYPE_OVERRIDES import"
```

---

### Task 21: Run tests to verify

- [ ] **Step 1: Run existing tests**

```bash
cd /home/mint/dev/9router-fastapi
python -m pytest backend/tests/ -v -k "provider" --tb=short
```

Expected: All provider-related tests pass

- [ ] **Step 2: Manual verification**

Test `infer_model_type()` with a few examples:
```python
python -c "
from app.routers.providers.constants import infer_model_type
print(infer_model_type('whisper-1'))      # Should be 'stt'
print(infer_model_type('text-embedding-3-small'))  # Should be 'embedding'
print(infer_model_type('gpt-4'))          # Should be 'llm'
"
```

Expected output:
```
stt
embedding
llm
```

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "feat(providers): distribute MODEL_TYPE_OVERRIDES to per-provider configs"
```

---

## Success Criteria

1. `MODEL_TYPE_OVERRIDES` removed from `constants.py` (no hardcoded dict)
2. Each provider defines its own overrides in `config.py`
3. `get_all_model_type_overrides()` aggregates all overrides
4. `infer_model_type()` still works correctly
5. All existing tests pass
6. No circular imports

---

## Notes

- **Nomic/BAAI models:** `nomic-ai/nomic-embed-text-v1.5` and `BAAI/bge-large-en-v1.5` are hosted on multiple providers (Together, HuggingFace). They should stay in the provider where they're most commonly used (e.g., Together for nomic, HuggingFace for BAAI).
- **Caching:** `_get_model_type_overrides()` uses module-level cache. This is fine for production (server starts once). For tests, may need to clear cache between test runs.
- **Backward compatibility:** Keep `MODEL_TYPE_OVERRIDES` reference in constants.py for any external code that imports it directly.
