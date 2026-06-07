# Qoder Consolidation — Pindahkan services/qoder/ ke providers/qoder/

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Pindahkan semua file dari `backend/app/services/qoder/` ke `backend/app/providers/qoder/` sehingga semua Qoder-specific code berada di satu lokasi. Hapus `services/qoder/` setelah migrasi selesai.

**Architecture:** Copy files, update imports, delete old directory.

---

## Problem

Qoder-specific code tersebar di 2 lokasi:

```
backend/app/services/qoder/     ← 6 files, 1274 baris (crypto, auth, models)
backend/app/providers/qoder/    ← 3 files (config, handler, __init__)
```

**Masalah:**
- Update Qoder API? Harus cek 2 folder
- Hapus Qoder? Harus hapus 2 folder
- Import `from app.services.qoder.cosy import ...` di proxy.py → melanggar prinsip single-location
- Tidak konsisten dengan provider lain (semua di `providers/<name>/`)

**Solusi:** Pindahkan semua isi `services/qoder/` ke `providers/qoder/`, update semua import, hapus `services/qoder/`.

---

## File Mapping

| Dari | Ke | Status |
|------|-----|--------|
| `services/qoder/__init__.py` | `providers/qoder/__init__.py` | Merge (update exports) |
| `services/qoder/auth.py` | `providers/qoder/auth.py` | Move |
| `services/qoder/constants.py` | `providers/qoder/constants.py` | Move |
| `services/qoder/cosy.py` | `providers/qoder/cosy.py` | Move |
| `services/qoder/encoding.py` | `providers/qoder/encoding.py` | Move |
| `services/qoder/models.py` | `providers/qoder/models.py` | Move |
| `services/qoder/transform.py` | `providers/qoder/transform.py` | Move |

---

## Import Updates

### Yang perlu diupdate (imports dari `services.qoder`):

| File | Import Lama | Import Baru |
|------|-------------|-------------|
| `providers/qoder/handler.py` | `from app.services.qoder.cosy import ...` | `from app.providers.qoder.cosy import ...` |
| `providers/qoder/handler.py` | `from app.services.qoder.constants import ...` | `from app.providers.qoder.constants import ...` |
| `providers/qoder/handler.py` | `from app.services.qoder.transform import ...` | `from app.providers.qoder.transform import ...` |
| `providers/qoder/handler.py` | `from app.services.qoder.models import ...` | `from app.providers.qoder.models import ...` |
| `providers/qoder/handler.py` | `from app.services.qoder.encoding import ...` | `from app.providers.qoder.encoding import ...` |
| `routers/oauth.py` | `from app.services.qoder.auth import import_pat` | `from app.providers.qoder.auth import import_pat` |
| `services/oauth_providers.py` | `from app.services.qoder.auth import initiate_device_flow` | `from app.providers.qoder.auth import initiate_device_flow` |
| `services/oauth_providers.py` | `from app.services.qoder.auth import poll_device_token` | `from app.providers.qoder.auth import poll_device_token` |

### Yang sudah OK (tidak perlu diupdate):

| File | Alasan |
|------|--------|
| `providers/qoder/config.py` | Tidak import dari services |
| `providers/qoder/auth.py` | Internal imports (relative) |
| `providers/qoder/cosy.py` | Internal imports (relative) |
| `providers/qoder/encoding.py` | Internal imports (relative) |
| `providers/qoder/models.py` | Internal imports (relative) |
| `providers/qoder/transform.py` | Internal imports (relative) |

---

## Tasks

### Task 1: Copy auth.py ke providers/qoder/

**Files:**
- Copy: `services/qoder/auth.py` → `providers/qoder/auth.py`

- [ ] **Step 1: Copy file**

```bash
cp backend/app/services/qoder/auth.py backend/app/providers/qoder/auth.py
```

- [ ] **Step 2: Update internal imports (jika ada)**

Check dan update imports di dalam auth.py yang mungkin pakai relative imports ke services/qoder/:

```python
# Before (jika ada):
from .constants import QODER_DEVICE_TOKEN_URL, ...

# After (tetap sama, karena file dipindah ke folder yang sama):
from .constants import QODER_DEVICE_TOKEN_URL, ...
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/qoder/auth.py
git commit -m "feat(qoder): move auth.py from services to providers"
```

---

### Task 2: Copy constants.py ke providers/qoder/

**Files:**
- Copy: `services/qoder/constants.py` → `providers/qoder/constants.py`

- [ ] **Step 1: Copy file**

```bash
cp backend/app/services/qoder/constants.py backend/app/providers/qoder/constants.py
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/qoder/constants.py
git commit -m "feat(qoder): move constants.py from services to providers"
```

---

### Task 3: Copy cosy.py ke providers/qoder/

**Files:**
- Copy: `services/qoder/cosy.py` → `providers/qoder/cosy.py`

- [ ] **Step 1: Copy file**

```bash
cp backend/app/services/qoder/cosy.py backend/app/providers/qoder/cosy.py
```

- [ ] **Step 2: Update internal imports**

cosy.py import dari constants.py — sudah OK karena relative import:

```python
from .constants import (
    QODER_CLIENT_TYPE,
    QODER_DATA_POLICY,
    ...
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/qoder/cosy.py
git commit -m "feat(qoder): move cosy.py from services to providers"
```

---

### Task 4: Copy encoding.py ke providers/qoder/

**Files:**
- Copy: `services/qoder/encoding.py` → `providers/qoder/encoding.py`

- [ ] **Step 1: Copy file**

```bash
cp backend/app/services/qoder/encoding.py backend/app/providers/qoder/encoding.py
```

- [ ] **Step 2: Update internal imports**

encoding.py import dari constants.py — sudah OK:

```python
from .constants import QODER_STD_ALPHABET, QODER_CUSTOM_ALPHABET
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/qoder/encoding.py
git commit -m "feat(qoder): move encoding.py from services to providers"
```

---

### Task 5: Copy models.py ke providers/qoder/

**Files:**
- Copy: `services/qoder/models.py` → `providers/qoder/models.py`

- [ ] **Step 1: Copy file**

```bash
cp backend/app/services/qoder/models.py backend/app/providers/qoder/models.py
```

- [ ] **Step 2: Update internal imports**

models.py import dari constants.py dan cosy.py — sudah OK:

```python
from .constants import QODER_MODEL_LIST_URL
from .cosy import build_cosy_headers
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/qoder/models.py
git commit -m "feat(qoder): move models.py from services to providers"
```

---

### Task 6: Copy transform.py ke providers/qoder/

**Files:**
- Copy: `services/qoder/transform.py` → `providers/qoder/transform.py`

- [ ] **Step 1: Copy file**

```bash
cp backend/app/services/qoder/transform.py backend/app/providers/qoder/transform.py
```

- [ ] **Step 2: Update internal imports**

transform.py import dari constants.py — sudah OK:

```python
from .constants import QODER_MODEL_MAP
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/qoder/transform.py
git commit -m "feat(qoder): move transform.py from services to providers"
```

---

### Task 7: Update providers/qoder/__init__.py

**Files:**
- Modify: `backend/app/providers/qoder/__init__.py`

- [ ] **Step 1: Merge exports dari services/qoder/__init__.py**

```python
"""Qoder provider module.

All Qoder-specific code lives here:
- auth: OAuth device flow + PAT import
- constants: URLs, COSY constants
- cosy: COSY signing (RSA + AES + MD5)
- encoding: WAF-bypass body encoding
- models: Model catalog fetching
- transform: Request/response transformation
- config: Provider configuration
- handler: Handler methods
"""

from .auth import (
    generate_pkce_pair,
    initiate_device_flow,
    poll_device_token,
    fetch_user_info,
    exchange_personal_token,
    import_pat,
)
from .cosy import (
    build_cosy_headers,
    generate_machine_id,
)
from .encoding import qoder_encode_body
from .models import (
    resolve_qoder_models,
    get_qoder_model_config,
    fetch_qoder_catalog,
)
from .constants import (
    QODER_MODEL_MAP,
    QODER_CHAT_URL_ENCODED,
    QODER_QUOTA_USAGE_URL,
)

__all__ = [
    "generate_pkce_pair",
    "initiate_device_flow",
    "poll_device_token",
    "fetch_user_info",
    "exchange_personal_token",
    "import_pat",
    "build_cosy_headers",
    "generate_machine_id",
    "qoder_encode_body",
    "resolve_qoder_models",
    "get_qoder_model_config",
    "fetch_qoder_catalog",
    "QODER_MODEL_MAP",
    "QODER_CHAT_URL_ENCODED",
    "QODER_QUOTA_USAGE_URL",
]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/qoder/__init__.py
git commit -m "feat(qoder): update __init__.py with all exports"
```

---

### Task 8: Update providers/qoder/handler.py — fix imports

**Files:**
- Modify: `backend/app/providers/qoder/handler.py`

- [ ] **Step 1: Update all imports dari services.qoder ke providers.qoder**

```python
# Before:
from app.services.qoder.constants import QODER_CHAT_URL_ENCODED
from app.services.qoder.cosy import build_cosy_headers
from app.services.qoder.transform import build_qoder_request_body
from app.services.qoder.models import get_qoder_model_config, resolve_qoder_models
from app.services.qoder.encoding import qoder_encode_body
from app.services.qoder.transform import unwrap_qoder_response

# After:
from app.providers.qoder.constants import QODER_CHAT_URL_ENCODED
from app.providers.qoder.cosy import build_cosy_headers
from app.providers.qoder.transform import build_qoder_request_body
from app.providers.qoder.models import get_qoder_model_config, resolve_qoder_models
from app.providers.qoder.encoding import qoder_encode_body
from app.providers.qoder.transform import unwrap_qoder_response
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/qoder/handler.py
git commit -m "refactor(qoder): update handler imports to use providers.qoder"
```

---

### Task 9: Update routers/oauth.py — fix import

**Files:**
- Modify: `backend/app/routers/oauth.py`

- [ ] **Step 1: Update import**

```python
# Before:
from app.services.qoder.auth import import_pat

# After:
from app.providers.qoder.auth import import_pat
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/oauth.py
git commit -m "refactor(oauth): update qoder import to use providers.qoder"
```

---

### Task 10: Update services/oauth_providers.py — fix imports

**Files:**
- Modify: `backend/app/services/oauth_providers.py`

- [ ] **Step 1: Update imports**

```python
# Before:
from app.services.qoder.auth import initiate_device_flow
from app.services.qoder.auth import poll_device_token

# After:
from app.providers.qoder.auth import initiate_device_flow
from app.providers.qoder.auth import poll_device_token
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/oauth_providers.py
git commit -m "refactor(oauth_providers): update qoder imports to use providers.qoder"
```

---

### Task 11: Delete services/qoder/

**Files:**
- Delete: `backend/app/services/qoder/` (entire directory)

- [ ] **Step 1: Verify no remaining imports**

```bash
grep -rn "from app.services.qoder\|from app\.services\.qoder" backend/app/ --include="*.py" | grep -v __pycache__
```

Expected: No results (all imports updated)

- [ ] **Step 2: Delete directory**

```bash
rm -rf backend/app/services/qoder/
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor(qoder): remove services/qoder/ (moved to providers/qoder/)"
```

---

### Task 12: Verify — full integration test

- [ ] **Step 1: Test imports**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -c "
# Test all imports from new location
from app.providers.qoder.auth import initiate_device_flow, poll_device_token, import_pat
from app.providers.qoder.constants import QODER_CHAT_URL_ENCODED, QODER_MODEL_MAP
from app.providers.qoder.cosy import build_cosy_headers, generate_machine_id
from app.providers.qoder.encoding import qoder_encode_body
from app.providers.qoder.models import resolve_qoder_models, get_qoder_model_config
from app.providers.qoder.transform import build_qoder_request_body, unwrap_qoder_response
from app.providers.qoder.config import QoderConfig
from app.providers.qoder.handler import QoderHandler

print('All imports OK!')
print(f'QODER_CHAT_URL_ENCODED: {QODER_CHAT_URL_ENCODED[:50]}...')
print(f'QoderConfig.PROVIDER_NAME: {QoderConfig().PROVIDER_NAME}')
"
```

- [ ] **Step 2: Test handler loading**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -c "
from app.providers.provider import Provider

p = Provider('qoder')
h = p.handler()
print(f'Handler: {type(h).__name__}')
print(f'Config: {p.config().PROVIDER_NAME}')
print(f'Alias: {p.config().ALIAS}')

# Test URL building
url = h.build_upstream_url('https://api3.qoder.sh')
print(f'URL: {url}')
"
```

- [ ] **Step 3: Run tests**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -m pytest tests/ -v --tb=short --ignore=tests/test_provider_models-v1.py
```

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat(qoder): complete consolidation to providers/qoder/"
```

---

## Final Structure

```
backend/app/providers/qoder/
├── __init__.py      ← Package exports
├── config.py        ← Provider config (PROVIDER_NAME, ALIAS, etc.)
├── handler.py       ← Handler methods (build_url, build_headers, etc.)
├── auth.py          ← OAuth device flow + PAT import
├── constants.py     ← URLs, COSY constants
├── cosy.py          ← COSY signing (RSA + AES + MD5)
├── encoding.py      ← WAF-bypass body encoding
├── models.py        ← Model catalog fetching
└── transform.py     ← Request/response transformation

backend/app/services/qoder/    ← DELETED (sudah dipindah)
```

---

## Success Criteria

1. `backend/app/services/qoder/` sudah tidak ada
2. Semua file ada di `backend/app/providers/qoder/`
3. Tidak ada import `from app.services.qoder` di manapun
4. Semua import pakai `from app.providers.qoder`
5. `Provider("qoder").handler()` tetap work
6. OAuth device flow tetap work
7. PAT import tetap work
8. COSY signing tetap work
9. Semua existing tests pass

---

## Dependency Order

```
Task 1-6  (copy files) ─────────────────────┐
Task 7    (update __init__.py) ──────────────┤
Task 8    (update handler.py imports) ───────┼──► Task 11 (delete services/qoder/)
Task 9    (update oauth.py imports) ─────────┤           │
Task 10   (update oauth_providers.py imports)┘           ▼
                                              Task 12 (verify)
```

Tasks 1-6 bisa parallel. Tasks 8-10 bisa parallel. Task 11 harus terakhir.

---

## Notes

- **Internal imports OK** — File-file qoder pakai relative imports (`from .constants import ...`), jadi setelah dipindah ke folder yang sama, imports tetap work.
- **External imports** — Hanya 3 file yang import dari `services.qoder`: handler.py, oauth.py, oauth_providers.py.
- **OAuth flow** — `routers/oauth.py` dan `services/oauth_providers.py` import `auth.py` functions. Setelah update import, flow tetap sama.
- **PLAN-PROXY-INTEGRATION** — Plan ini bisa di-eksekusi sebelum atau sesudah PLAN-PROXY-INTEGRATION, karena handler.py sudah diupdate di Task 8.
