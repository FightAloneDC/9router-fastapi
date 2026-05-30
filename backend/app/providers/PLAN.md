# Providers Architecture Plan

> **Status**: Draft / Future Planning
> **Purpose**: Dokumen ini menangkap visi arsitektur `backend/app/providers/` untuk pengembangan ke depan.

---

## 1. Visi

Setiap provider memiliki **folder sendiri** yang berisi **semua logic provider-specific** — bukan hanya config, tapi juga adapter handlers (TTS, STT, search, models, dll.).

Tujuan akhir: **DRY architecture** di mana file-file di `backend/app/services/` (seperti `tts_adapters.py`, `stt_adapters.py`, `search_adapters.py`) menjadi **thin dispatcher** yang me-resolve ke handler per-provider.

---

## 2. Struktur Folder Target

```
backend/app/providers/
├── __init__.py                  # Package entry point, exports Provider() helper
├── base.py                      # Base classes / abstract interfaces
├── provider.py                  # Provider() factory/helper class
├── PLAN.md                      # Dokumen ini
│
├── cerebras/
│   ├── __init__.py
│   ├── config.py                # CerebrasConfig (Pydantic model)
│   ├── tts.py                   # TTS handler
│   ├── stt.py                   # STT handler (jika ada)
│   ├── models.py                # Model fetching logic
│   └── search.py                # Search handler (jika ada)
│
├── openai/
│   ├── __init__.py
│   ├── config.py                # OpenAIConfig
│   ├── tts.py
│   ├── stt.py
│   ├── models.py
│   └── embeddings.py
│
├── anthropic/
│   ├── __init__.py
│   ├── config.py                # AnthropicConfig (x-api-key auth)
│   └── models.py
│
├── google/
│   ├── __init__.py
│   ├── config.py                # GoogleConfig (query param auth)
│   ├── tts.py
│   ├── stt.py
│   └── models.py
│
├── azure/
│   ├── __init__.py
│   ├── config.py                # AzureConfig (data-driven URL)
│   ├── tts.py
│   ├── stt.py
│   └── models.py
│
├── elevenlabs/
│   ├── __init__.py
│   ├── config.py                # ElevenLabsConfig (xi-api-key)
│   └── tts.py
│
├── deepgram/
│   ├── __init__.py
│   ├── config.py                # DeepgramConfig (Token prefix)
│   ├── tts.py
│   └── stt.py
│
├── ... (90+ provider folders)
│
└── _template/
    ├── __init__.py
    ├── config.py                # Template config untuk provider baru
    ├── tts.py                   # Template handler
    └── README.md                # Cara menambah provider baru
```

---

## 3. Config Pattern (Pydantic)

Setiap provider punya `config.py` dengan Pydantic model yang mendefinisikan semua konfigurasi provider.

### 3.1 Base Config

```python
# backend/app/providers/base.py
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class AuthType(str, Enum):
    """Tipe autentikasi yang didukung."""
    API_KEY = "apikey"           # Bearer token (Authorization: Bearer <key>)
    X_API_KEY = "x-api-key"     # Anthropic-style (x-api-key: <key>)
    QUERY_PARAM = "query_param" # Google-style (?key=<key>)
    AZURE_KEY = "azure_key"     # Azure (api-key: <key>)
    OAUTH = "oauth"             # OAuth (various flows)
    COOKIE = "cookie"           # Cookie-based (grok-web, perplexity-web)
    NONE = "none"               # No auth (ollama, edge-tts, searxng)
    CUSTOM = "custom"           # Provider-specific (elevenlabs, deepgram, dll.)

class ProviderFormat(str, Enum):
    """Format request/response yang didukung."""
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    AZURE = "azure"

class ProviderModelFetchConfig(BaseModel):
    """Konfigurasi untuk fetch model list dari provider."""
    model_config = {"frozen": True}

    url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    authHeader: Optional[str] = None
    authPrefix: Optional[str] = None
    authQuery: Optional[str] = None
    responseKey: str = "data"

    def parseResponse(self, data: dict) -> list:
        return data.get(self.responseKey, [])
```

### 3.2 Provider Config (per-provider)

**PENTING: Jangan hardcode URL yang sudah ada di BASE_URL!**

`MODEL_FETCH.url` harus derive dari `BASE_URL` menggunakan `@computed_field` (Pydantic v2) agar tetap DRY.

```python
# backend/app/providers/cerebras/config.py
from pydantic import BaseModel, Field, computed_field
from app.providers.base import AuthType, ProviderFormat, ProviderModelFetchConfig

class CerebrasConfig(BaseModel):
    """Cerebras-specific configuration."""
    model_config = {"frozen": True}

    # Identity
    PROVIDER_ID: str = "cerebras"
    PROVIDER_NAME: str = "Cerebras"
    MODEL_PREFIX: str = "cb"

    # API
    BASE_URL: str = "https://api.cerebras.ai/v1"
    FORMAT: ProviderFormat = ProviderFormat.OPENAI

    # Auth
    AUTH_TYPE: AuthType = AuthType.API_KEY
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer"

    # Models
    DEFAULT_MODELS: list[str] = Field(default_factory=lambda: [
        "llama3.1-8b", "llama3.1-70b", "llama-3.3-70b",
    ])

    # Model fetch endpoint (relative path, di-append ke BASE_URL)
    MODEL_FETCH_PATH: str = "/models"

    @computed_field
    @property
    def MODEL_FETCH(self) -> ProviderModelFetchConfig:
        """Derive model fetch URL dari BASE_URL + MODEL_FETCH_PATH."""
        return ProviderModelFetchConfig(
            url=f"{self.BASE_URL}{self.MODEL_FETCH_PATH}",
            headers={"Content-Type": "application/json"},
            authHeader=self.AUTH_HEADER,
            authPrefix=f"{self.AUTH_PREFIX} ",
            responseKey="data",
        )
```

**Kenapa ini penting:**
- Jika `BASE_URL` berubah, `MODEL_FETCH.url` otomatis ikut berubah
- Tidak ada duplikasi URL yang bisa diveriasi
- `AUTH_HEADER` dan `AUTH_PREFIX` juga di-reuse dari field yang sama

### 3.3 Contoh Auth Variations

```python
# Anthropic (x-api-key)
class AnthropicConfig(BaseModel):
    AUTH_TYPE: AuthType = AuthType.X_API_KEY
    AUTH_HEADER: str = "x-api-key"
    AUTH_PREFIX: str = ""  # No prefix
    EXTRA_HEADERS: dict[str, str] = {"anthropic-version": "2023-06-01"}

# Google (query param)
class GoogleConfig(BaseModel):
    AUTH_TYPE: AuthType = AuthType.QUERY_PARAM
    AUTH_QUERY: str = "key"

# Azure (api-key + data-driven URL)
class AzureConfig(BaseModel):
    AUTH_TYPE: AuthType = AuthType.AZURE_KEY
    AUTH_HEADER: str = "api-key"
    # URL dibangun dari: azureEndpoint + /deployments/{deployment}/...
    AZURE_ENDPOINT: str = ""
    DEPLOYMENT: str = ""
    API_VERSION: str = "2024-02-01"

# ElevenLabs (custom header)
class ElevenLabsConfig(BaseModel):
    AUTH_TYPE: AuthType = AuthType.CUSTOM
    AUTH_HEADER: str = "xi-api-key"
    AUTH_PREFIX: str = ""

# Deepgram (Token prefix, bukan Bearer)
class DeepgramConfig(BaseModel):
    AUTH_TYPE: AuthType = AuthType.CUSTOM
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Token"

# No auth (ollama, edge-tts)
class OllamaConfig(BaseModel):
    AUTH_TYPE: AuthType = AuthType.NONE
    BASE_URL: str = "http://localhost:11434"
```

---

## 4. Provider Helper / Factory

`Provider('cerebras')` adalah unified accessor yang me-resolve ke config class yang tepat.

```python
# backend/app/providers/provider.py
from typing import Type
from pydantic import BaseModel
from app.providers.cerebras.config import CerebrasConfig
# from app.providers.openai.config import OpenAIConfig
# from app.providers.anthropic.config import AnthropicConfig
# ...

_REGISTRY: dict[str, Type[BaseModel]] = {
    "cerebras": CerebrasConfig,
    # "openai": OpenAIConfig,
    # "anthropic": AnthropicConfig,
}

class Provider:
    """Unified accessor untuk provider configs."""

    def __init__(self, name: str) -> None:
        if name not in _REGISTRY:
            raise ValueError(f"Unknown provider: {name}")
        self._name = name
        self._config = _REGISTRY[name]()

    def base_url(self) -> str:
        return self._config.BASE_URL

    def prefix(self) -> str:
        return self._config.MODEL_PREFIX

    def auth_type(self) -> str:
        return self._config.AUTH_TYPE

    def auth_header(self) -> str:
        return self._config.AUTH_HEADER

    def auth_prefix(self) -> str:
        return self._config.AUTH_PREFIX

    def format(self) -> str:
        return self._config.FORMAT

    def set_models(self, models: list[str]) -> None:
        self._config = self._config.model_copy(update={"DEFAULT_MODELS": models})

    def models(self) -> list[str]:
        return self._config.DEFAULT_MODELS

    def config(self) -> BaseModel:
        return self._config
```

**Usage:**
```python
Provider('cerebras').base_url()    # -> "https://api.cerebras.ai/v1"
Provider('cerebras').prefix()      # -> "cb"
Provider('cerebras').auth_type()   # -> "apikey"
Provider('anthropic').auth_header() # -> "x-api-key"
Provider('google').auth_type()     # -> "query_param"
```

---

## 5. Adapter Pattern (TTS, STT, Search, dll.)

### 5.1 Sekarang (scattered)

```python
# backend/app/services/tts_adapters.py
TTS_ADAPTERS = {
    "openai": tts_openai,
    "elevenlabs": tts_elevenlabs,
    "deepgram": tts_deepgram,
    "gemini": tts_gemini,
    # ... 16 handlers di 1 file
}

def tts_openai(target, body, request_id): ...
def tts_elevenlabs(target, body, request_id): ...
def tts_deepgram(target, body, request_id): ...
# ...
```

### 5.2 Visi (per-provider)

```python
# backend/app/providers/openai/tts.py
def handle(target: ProxyTarget, body: dict, request_id: str) -> Response:
    """OpenAI-specific TTS handler."""
    config = Provider('openai').config()
    # ... logic OpenAI TTS
```

```python
# backend/app/providers/elevenlabs/tts.py
def handle(target: ProxyTarget, body: dict, request_id: str) -> Response:
    """ElevenLabs-specific TTS handler."""
    config = Provider('elevenlabs').config()
    # ... logic ElevenLabs TTS (xi-api-key, voice in URL)
```

### 5.3 Thin Dispatcher di services/

```python
# backend/app/services/tts_adapters.py (versi DRY)
import importlib

def get_tts_adapter(provider: str):
    """Resolve TTS adapter untuk provider."""
    try:
        module = importlib.import_module(f"app.providers.{provider}.tts")
        return module.handle
    except ModuleNotFoundError:
        raise ValueError(f"No TTS adapter for provider: {provider}")

# Atau dengan registry pattern:
from app.providers.openai.tts import handle as openai_tts
from app.providers.elevenlabs.tts import handle as elevenlabs_tts
# ...

TTS_ADAPTERS: dict[str, Callable] = {
    "openai": openai_tts,
    "elevenlabs": elevenlabs_tts,
    # ... auto-populated dari provider folders
}
```

---

## 6. Auth Method Mapping

| AuthType | Header | Prefix | Query | Contoh Provider |
|---|---|---|---|---|
| `API_KEY` | `Authorization` | `Bearer` | - | openai, cerebras, deepseek, groq |
| `X_API_KEY` | `x-api-key` | *(kosong)* | - | anthropic, glm, kimi |
| `QUERY_PARAM` | - | - | `key` | google, gemini |
| `AZURE_KEY` | `api-key` | *(kosong)* | - | azure |
| `OAUTH` | `Authorization` | `Bearer` | - | claude, codex, github |
| `COOKIE` | `Cookie` | - | - | grok-web, perplexity-web |
| `NONE` | - | - | - | ollama, edge-tts, searxng |
| `CUSTOM` | *(varies)* | *(varies)* | - | elevenlabs, deepgram, playht |

---

## 7. Migration Path

### Phase 1: Foundation (Draft — saat ini)
- [x] Buat folder structure per-provider (cerebras, openrouter)
- [x] Buat `CerebrasConfig` Pydantic model
- [x] Buat `Provider()` helper class
- [ ] Dokumentasi plan (dokumen ini)

### Phase 2: Config Completion
- [ ] Buat config class untuk semua provider yang ada di `PROVIDER_CONFIGS`
- [ ] Buat `AuthType` dan `ProviderFormat` enums
- [ ] Buat base config class dengan field umum
- [ ] Validasi bahwa config class bisa replace dict-based `PROVIDER_CONFIGS`

### Phase 3: Adapter Migration
- [ ] Pindahkan TTS handlers dari `services/tts_adapters.py` ke per-provider
- [ ] Pindahkan STT handlers dari `services/stt_adapters.py` ke per-provider
- [ ] Pindahkan Search handlers dari `services/search_adapters.py` ke per-provider
- [ ] Buat thin dispatcher di `services/` yang call ke provider folders

### Phase 4: Proxy Integration
- [ ] Refactor `services/proxy.py` untuk gunakan `Provider()` helper
- [ ] Replace `PROVIDER_CONFIGS` dict dengan config class instances
- [ ] Replace `ALIAS_TO_ID` dengan registry di `providers/__init__.py`

### Phase 5: Cleanup
- [ ] Hapus dead code di `services/`
- [ ] Update tests
- [ ] Dokumentasi cara menambah provider baru

---

## 8. Contoh: Menambah Provider Baru

### Cara lama (scattered):
1. Tambah entry di `PROVIDER_CONFIGS` di `proxy.py`
2. Tambah entry di `PROVIDER_DEFAULTS` di `constants.py`
3. Tambah entry di `PROVIDER_MODELS_CONFIG` di `models.py`
4. Tambah handler di `tts_adapters.py` (jika support TTS)
5. Tambah handler di `stt_adapters.py` (jika support STT)
6. Tambah validation di `validation.py`
7. Update `.env` dengan API key

### Cara baru (per-provider):
1. Buat folder `backend/app/providers/new_provider/`
2. Buat `config.py` dengan config class
3. Buat `tts.py` / `stt.py` / `models.py` sesuai kebutuhan
4. Tambah entry di `provider.py` registry
5. Selesai — dispatcher otomatis resolve ke folder

---

## 9. Catatan Penting

- **Jangan integrasikan ke core sampai Phase 2 selesai** — folder `providers/` masih draft
- **Backup files (`-v*`) jangan disentuh** — itu safety net
- **Existing system tetap jalan** — `PROVIDER_CONFIGS` di `proxy.py` tetap aktif sampai migration selesai
- **Pydantic `frozen=True`** — config immutable, gunakan `model_copy(update={...})` untuk update
- **OAuth tetap di `services/oauth_providers.py`** — OAuth flow terlalu kompleks untuk per-provider folder (bisa dievaluasi ulang nanti)
- **⚠️ DRY PRINSIP: Jangan hardcode URL/headers yang sudah ada di field lain!**
  - `MODEL_FETCH.url` harus derive dari `BASE_URL` + `MODEL_FETCH_PATH`
  - `MODEL_FETCH.authHeader` harus reuse dari `AUTH_HEADER`
  - `MODEL_FETCH.authPrefix` harus reuse dari `AUTH_PREFIX`
  - Gunakan `@computed_field` (Pydantic v2) untuk derive otomatis
  - Jika ada URL/headers yang diulang, itu tanda perlu refactor

---

## 10. Referensi File Existing

File-file ini akan terpengaruh saat migration:

| File | Status | Notes |
|---|---|---|
| `services/proxy.py` | Aktif | `PROVIDER_CONFIGS`, `ALIAS_TO_ID` akan di-replace |
| `services/tts_adapters.py` | Aktif | 16 handlers akan pindah ke per-provider |
| `services/stt_adapters.py` | Aktif | 7 handlers akan pindah ke per-provider |
| `services/search_adapters.py` | Aktif | 10 handlers akan pindah ke per-provider |
| `services/oauth_providers.py` | Aktif | 14 OAuth configs — evaluasi ulang nanti |
| `routers/providers/constants.py` | Aktif | `PROVIDER_DEFAULTS` akan di-replace |
| `routers/providers/models.py` | Aktif | `PROVIDER_MODELS_CONFIG` akan di-replace |
| `routers/providers/validation.py` | Aktif | 15 validation functions akan pindah |

---

*Dokumen ini akan diupdate seiring progress implementasi.*
