# Providers Architecture

> **Status**: Implemented (Cerebras, Groq, OpenRouter)
> **Last updated**: 2026-05-31

---

## 1. Core Principles

### Constants Over Strings

All provider name references MUST go through constants defined in `__init__.py`.
No string literals for provider names anywhere in the codebase.

```python
# ❌ WRONG — string literal scattered in code
Provider("cerebras")
for name in ["cerebras", "groq", "openrouter"]: ...

# ✅ CORRECT — single source of truth
Provider(PROVIDER_CEREBRAS)
for name in AVAILABLE_PROVIDERS: ...
```

### Single Source of Truth

Each provider has ONE config file. All derived values (URL, headers, auth) come
from that config. No duplication across files.

### Provider Class as Unified Accessor

Never import per-provider modules directly when working with multiple providers.
Use the `Provider` class which lazy-loads config and models.

---

## 2. Folder Structure

```
backend/app/providers/
├── __init__.py          # Constants: PROVIDER_*, AVAILABLE_PROVIDERS
├── provider.py          # Provider class — unified accessor
├── ARCHITECTURE.md      # This document
│
├── cerebras/
│   ├── __init__.py      # """Cerebras provider."""
│   ├── config.py        # CerebrasConfig + CerebrasMetadata
│   └── models.py        # fetch_models(), parse_response()
│
├── groq/
│   ├── __init__.py
│   ├── config.py        # GroqConfig + GroqMetadata
│   └── models.py        # fetch_models(), parse_response()
│
└── openrouter/
    ├── __init__.py
    ├── config.py        # OpenRouterConfig + OpenRouterMetadata
    └── models.py        # fetch_models(), parse_response()
```

---

## 3. File Roles

### `__init__.py` — Constants

Defines provider name constants and the `AVAILABLE_PROVIDERS` list.

```python
PROVIDER_CEREBRAS = "cerebras"
PROVIDER_GROQ = "groq"
PROVIDER_OPENROUTER = "openrouter"

AVAILABLE_PROVIDERS: list[str] = [
    PROVIDER_CEREBRAS,
    PROVIDER_GROQ,
    PROVIDER_OPENROUTER,
]
```

Adding a new provider:
1. Add constant: `PROVIDER_NEW = "new"`
2. Append to `AVAILABLE_PROVIDERS`

### `provider.py` — Provider Class

Unified accessor that lazy-loads config and models per provider.

```python
from app.providers import PROVIDER_CEREBRAS
from app.providers.provider import Provider

p = Provider(PROVIDER_CEREBRAS)
p.config()            # CerebrasConfig instance
p.base_url()          # "https://api.cerebras.ai/v1"
p.alias()             # "cb"
p.parse_response({})  # []
await p.fetch_models(api_key)
```

Uses `importlib` for lazy loading — no circular imports, no upfront imports.

### `config.py` — Provider Configuration

Two Pydantic models per provider:

```python
class CerebrasConfig(BaseModel):
    """Static provider characteristics."""
    PROVIDER_NAME: str = "Cerebras"
    PROVIDER_ID: str = "cerebras"
    ALIAS: str = "cb"
    BASE_URL: str = "https://api.cerebras.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ["llm"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}
    API_KEY: str = ""  # Runtime, from DB

class CerebrasMetadata(BaseModel):
    """UI display metadata."""
    name: str = "Cerebras"
    color: str = "#FF6B00"
    textIcon: str = "CB"
```

Config = technical. Metadata = UI. Separate concerns.

### `models.py` — Model Fetching

Each provider has its own `fetch_models()` and `parse_response()`.

```python
from app.providers.cerebras.config import CerebrasConfig
from app.utils.url import url_path_join

_config = CerebrasConfig()
MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")

def parse_response(data: dict) -> list:
    return data.get("data", [])

async def fetch_models(api_key: str) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        AUTH_HEADER: f"{AUTH_PREFIX}{api_key}",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(MODEL_FETCH_URL, headers=headers)
        resp.raise_for_status()
        return parse_response(resp.json())
```

URL is derived from config via `url_path_join` — never hardcoded.

---

## 4. URL Utility

`backend/app/utils/url.py` provides `url_path_join()` for building URLs.

```python
url_path_join("https://api.cerebras.ai/v1", "models")
# → "https://api.cerebras.ai/v1/models"

url_path_join("https://api.cerebras.ai/v1/", "/models")
# → "https://api.cerebras.ai/v1/models"
```

Uses `urllib.parse.urlparse` + `urlunparse`. Preserves query/fragment.
Default scheme: `https` if missing.

---

## 5. Test Architecture

Tests live in `backend/tests/test_provider_models.py`.

### Pattern: Loop, Don't Duplicate

```python
# ❌ WRONG — duplicate per provider
def test_cerebras_parse_response(): ...
def test_groq_parse_response(): ...
def test_openrouter_parse_response(): ...

# ✅ CORRECT — single test, loop all providers
def test_parse_response_normal():
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        assert len(p.parse_response({"data": [{"id": "x"}]})) == 1
```

### Pattern: Parametrize for Integration Tests

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("provider_id", AVAILABLE_PROVIDERS)
async def test_fetch_models_integration(provider_id: str):
    api_key = await get_api_key(provider_id)
    if not api_key:
        pytest.skip(f"No API key for {provider_id}")
    p = Provider(provider_id)
    models = await p.fetch_models(api_key)
    assert len(models) > 0
```

Adding a new provider = test automatically covers it.

### API Key Resolution

Integration tests resolve API key in order:
1. Environment variable (e.g. `CEREBRAS_API_KEY`)
2. Database `ProviderConnection.data["apiKey"]`

```python
async def get_api_key(provider_id: str) -> str | None:
    # 1. Env var
    env_var = _API_KEY_ENV_VARS.get(provider_id)
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]

    # 2. Database fallback
    await engine.dispose()  # Fix: clear stale connections from event loop
    async with async_session() as session:
        ...
```

### Event Loop Fix

pytest-asyncio creates a new event loop per test, but SQLAlchemy engine
connections are bound to the first loop. Fix: call `engine.dispose()` before
each DB query in tests.

---

## 6. Lessons Learned — Mistakes and Corrections

### Mistake 1: URL Joining with f-string

**Wrong:**
```python
MODEL_FETCH_URL = f"{_config.BASE_URL}/models"
```

**Problem:** Double slash if BASE_URL has trailing slash. Not DRY.

**Fix:** Use `url_path_join(_config.BASE_URL, "models")`.

### Mistake 2: URL Utility with while loop

**Wrong:**
```python
while "//" in path:
    path = path.replace("//", "/")
```

**Problem:** Terrible logic. Could strip scheme separator. Python has `urllib.parse`.

**Fix:** Use `urlparse` + `urlunparse` — standard library, correct by construction.

### Mistake 3: Unhandled ValueError

**Wrong:**
```python
def url_path_join(base, *parts):
    base = normalize_url(base)  # raises ValueError

# Caller never catches
```

**Problem:** `normalize_url` raises but caller doesn't handle. Silent crash.

**Fix:** Either handle in caller or don't raise — return empty string.

### Mistake 4: String literals for provider names

**Wrong:**
```python
Provider("cerebras")
for name in ["cerebras", "groq", "openrouter"]: ...
```

**Problem:** No type safety. Typo not caught. Refactoring requires find-replace.

**Fix:** Constants in `__init__.py`. All references go through `PROVIDER_CEREBRAS`.

### Mistake 5: DB query in test file

**Wrong:** Test imports `engine`, `async_session`, `ProviderConnection` to query
DB for API keys. This is caller logic, not test logic.

**Problem:** Test for `models.py` should test `models.py`, not database access.

**Fix:** Keep DB query only for integration test key resolution. Pure tests
(parse_response, URL derivation) don't touch DB.

### Mistake 6: Editing files without thinking

Multiple rounds of editing `url.py` — 5 iterations before getting it right.
Each iteration wasted tokens and user patience.

**Fix:** Think first. Read the requirements. Write once. Verify.

### Mistake 7: f-string in test after establishing url_path_join

Test file used `expected = f"{config.BASE_URL}/models"` while production code
used `url_path_join`. Inconsistent.

**Fix:** Test and production must use the same function.

---

## 7. Adding a New Provider

### Step-by-step

1. Create folder: `backend/app/providers/<name>/`
2. Create `__init__.py`: `"""<Name> provider."""`
3. Create `config.py`: `<Name>Config` + `<Name>Metadata` Pydantic models
4. Create `models.py`: `fetch_models()`, `parse_response()`, `MODEL_FETCH_URL`
5. Add constant to `providers/__init__.py`: `PROVIDER_<NAME> = "<name>"`
6. Append to `AVAILABLE_PROVIDERS`
7. Run tests — automatic coverage

### Config Template

```python
from pydantic import BaseModel


class <Name>Config(BaseModel):
    PROVIDER_NAME: str = "<Name>"
    PROVIDER_ID: str = "<name>"
    ALIAS: str = "<alias>"
    BASE_URL: str = "https://api.<name>.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ["llm"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}
    API_KEY: str = ""


class <Name>Metadata(BaseModel):
    name: str = "<Name>"
    color: str = "#000000"
    textIcon: str = "<XX>"
```

### Models Template

```python
import httpx
from app.providers.<name>.config import <Name>Config
from app.utils.url import url_path_join

_config = <Name>Config()
MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")
AUTH_HEADER = _config.AUTH_HEADER
AUTH_PREFIX = _config.AUTH_PREFIX
TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        AUTH_HEADER: f"{AUTH_PREFIX}{api_key}",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(MODEL_FETCH_URL, headers=headers)
        resp.raise_for_status()
        return parse_response(resp.json())
```

---

## 8. Test Before/After Restructuring

### Before: 15 imports, 15 test functions, string literals

```python
from app.providers.cerebras.config import CerebrasConfig
from app.providers.cerebras.models import parse_response as cerebras_parse
from app.providers.cerebras.models import fetch_models as cerebras_fetch
from app.providers.cerebras.models import MODEL_FETCH_URL as CEREBRAS_URL
from app.providers.groq.config import GroqConfig
from app.providers.groq.models import parse_response as groq_parse
from app.providers.groq.models import fetch_models as groq_fetch
from app.providers.groq.models import MODEL_FETCH_URL as GROQ_URL
from app.providers.openrouter.config import OpenRouterConfig
from app.providers.openrouter.models import parse_response as openrouter_parse
from app.providers.openrouter.models import fetch_models as openrouter_fetch
from app.providers.openrouter.models import MODEL_FETCH_URL as OPENROUTER_URL

def test_cerebras_parse_response_normal(): ...
def test_groq_parse_response_normal(): ...
def test_openrouter_parse_response_normal(): ...
def test_parse_response_empty_data():
    assert cerebras_parse({}) == []
    assert groq_parse({}) == []
    assert openrouter_parse({}) == []
# ... 12 more duplicate functions
```

### After: 7 imports, 11 test functions, constants + Provider class

```python
from app.providers import AVAILABLE_PROVIDERS, PROVIDER_CEREBRAS, PROVIDER_GROQ, PROVIDER_OPENROUTER
from app.providers.provider import Provider
from app.utils.url import url_path_join

def test_parse_response_normal():
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        assert len(p.parse_response({"data": [{"id": "x"}]})) == 1

@pytest.mark.asyncio
@pytest.mark.parametrize("provider_id", AVAILABLE_PROVIDERS)
async def test_fetch_models_integration(provider_id: str):
    api_key = await get_api_key(provider_id)
    if not api_key:
        pytest.skip(f"No API key for {provider_id}")
    p = Provider(provider_id)
    models = await p.fetch_models(api_key)
    assert len(models) > 0
```

### What Changed

| Aspect | Before | After |
|--------|--------|-------|
| Imports | 15 (per-provider manual) | 7 (constants + Provider class) |
| Test functions | 15 (duplicate per provider) | 11 (loop + parametrize) |
| Add new provider | Add 3 imports + 3 test functions | Add 1 constant to AVAILABLE_PROVIDERS |
| String literals | Yes | No |
| DB imports in test | Always imported | Only for integration tests |

---

*Document this architecture. Don't repeat the mistakes.*
