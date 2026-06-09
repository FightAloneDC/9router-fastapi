# Plan: Refactor `backend/app/routers/providers.py` (2150 lines)

## Problem

`providers.py` adalah monolith file 2150 lines yang mencampurkan banyak tanggung jawab:
- Provider defaults & constants
- Validation logic (7+ provider types)
- Test connection logic
- Provider Connection CRUD
- Provider Node CRUD
- Model fetching & management
- Proxy config helpers
- Data conversion utilities

File ini sulit di-maintain, sulit di-review, dan setiap perubahan kecil berisiko mempengaruhi seluruh file.

---

## Current File Structure (line ranges)

| Lines     | Section                          | LOC  | Responsibility                        |
|-----------|----------------------------------|------|---------------------------------------|
| 1-37      | Imports & router init            | 37   | Module setup                          |
| 39-116    | `PROVIDER_DEFAULTS`              | 78   | Provider default URLs & validation types |
| 118-129   | `_DATA_INTERNAL_KEYS`, `_SENSITIVE_KEYS` | 12 | Constants for data field classification |
| 132-144   | `_get_base_url`, `_get_validation_type` | 13 | Small helper functions               |
| 147-239   | `_connection_to_out`, `_sanitize_connection`, `_node_to_out` | 93 | Data conversion (DB model -> dict) |
| 242-280   | `_normalize_proxy_config`, `_normalize_proxy_pool_id` | 39 | Proxy config helpers |
| 283-497   | Validation functions             | 215  | `_validate_openai_compatible`, `_validate_anthropic`, `_validate_google`, `_validate_azure`, `_validate_cloudflare`, `_validate_openai_chat`, `_validate_ollama`, `_validate_vertex` |
| 499-640   | Test functions                   | 142  | `_test_openai_compatible`, `_test_anthropic_compatible`, `_test_provider_connection` |
| 643-702   | `POST /providers/validate`       | 60   | Validate provider credentials endpoint |
| 705-875   | Provider Connection CRUD         | 171  | `GET /providers`, `POST /providers`, etc. |
| 878-1003  | Batch test & suggested models    | 126  | `POST /providers/test-batch`, `GET /providers/suggested-models` |
| 1006-1187 | Individual provider endpoints    | 182  | `GET/PATCH/DELETE /providers/{conn_id}`, `POST /providers/{conn_id}/test` |
| 1190-1544 | `PROVIDER_MODELS_CONFIG`         | 355  | Provider-specific model fetch configs (dict with lambdas) |
| 1547-1757 | Model fetch/clear endpoints      | 211  | `GET /providers/{conn_id}/models`, `DELETE /providers/{conn_id}/models` |
| 1759-1971 | Provider Node CRUD               | 213  | `GET/POST/PUT/DELETE /provider-nodes` |
| 1974-2150 | Provider Node validation         | 177  | `POST /provider-nodes/validate` |

---

## Proposed New Structure

```
backend/app/routers/
├── providers/
│   ├── __init__.py                  # Re-exports router untuk backward compatibility
│   ├── _router.py                   # router = APIRouter(tags=["providers"])
│   ├── constants.py                 # PROVIDER_DEFAULTS, _DATA_INTERNAL_KEYS, _SENSITIVE_KEYS
│   ├── helpers.py                   # _get_base_url, _get_validation_type, data converters, proxy helpers
│   ├── validation.py                # Semua _validate_* functions
│   ├── testing.py                   # _test_* functions + POST /providers/validate + POST /providers/test-batch
│   ├── connections.py               # Provider Connection CRUD endpoints
│   ├── models.py                    # PROVIDER_MODELS_CONFIG + fetch/clear model endpoints
│   └── nodes.py                     # Provider Node CRUD + validation endpoints
```

---

## Detailed Breakdown

### 1. `providers/__init__.py` (backward compatibility)

```python
"""Provider routes — re-exports the combined router."""
from app.providers._router import router  # or however we combine
```

Agar tidak break existing imports di `main.py` yang meng-import `router` dari `app.routers.providers`.

---

### 2. `providers/_router.py`

```python
from fastapi import APIRouter
router = APIRouter(tags=["providers"])
```

Single source of truth untuk router instance. Setiap module endpoint akan import `router` dari sini dan register endpoint-nya.

---

### 3. `providers/constants.py` (~90 lines)

**Pindah dari providers.py:**
- `PROVIDER_DEFAULTS` (lines 39-116) — 78 lines
- `_DATA_INTERNAL_KEYS` (lines 118-126)
- `_SENSITIVE_KEYS` (lines 128-129)
- `SUGGESTED_MODELS_FILTERS` (lines 881-902)

---

### 4. `providers/helpers.py` (~130 lines)

**Pindah dari providers.py:**
- `_get_base_url()` (lines 132-139)
- `_get_validation_type()` (lines 142-144)
- `_connection_to_out()` (lines 147-188)
- `_sanitize_connection()` (lines 191-219)
- `_node_to_out()` (lines 222-239)
- `_normalize_proxy_config()` (lines 244-257)
- `_normalize_proxy_pool_id()` (lines 260-280)
- `_parse_openai_models()` (lines 1547-1553)
- `_normalize_model()` (lines 1556-1563)
- `_get_models_error_message()` (lines 1976-1983)
- `_get_chat_error_message()` (lines 1986-1995)

---

### 5. `providers/validation.py` (~220 lines)

**Pindah dari providers.py:**
- `_validate_openai_compatible()` (lines 285-315)
- `_validate_anthropic()` (lines 318-349)
- `_validate_google()` (lines 352-372)
- `_validate_azure()` (lines 375-399)
- `_validate_cloudflare()` (lines 402-428)
- `_validate_openai_chat()` (lines 431-455)
- `_validate_ollama()` (lines 458-474)
- `_validate_vertex()` (lines 477-496)

---

### 6. `providers/testing.py` (~200 lines)

**Pindah dari providers.py:**
- `_test_openai_compatible()` (lines 499-525)
- `_test_anthropic_compatible()` (lines 528-558)
- `_test_provider_connection()` (lines 561-640)
- `POST /providers/validate` endpoint (lines 643-702)
- `POST /providers/test-batch` endpoint (lines 905-977)

---

### 7. `providers/connections.py` (~350 lines)

**Pindah dari providers.py:**
- `GET /providers` — list_providers (lines 707-719)
- `GET /providers/client` — list_providers_client (lines 722-734)
- `POST /providers` — create_provider (lines 737-875)
- `GET /providers/{conn_id}` — get_provider (lines 1008-1024)
- `PATCH /providers/{conn_id}` — update_provider (lines 1027-1119)
- `DELETE /providers/{conn_id}` — delete_provider (lines 1122-1138)
- `POST /providers/{conn_id}/test` — test_provider (lines 1143-1187)
- `GET /providers/suggested-models` (lines 980-1003)

---

### 8. `providers/models.py` (~250 lines)

**Pindah dari providers.py:**
- `PROVIDER_MODELS_CONFIG` dict (lines 1192-1544) — **akan di-replace dengan import dari `app.provider.models.config`**
- `GET /providers/{conn_id}/models` — fetch_provider_models (lines 1566-1708)
- `DELETE /providers/{conn_id}/models` — clear_provider_models (lines 1711-1757)

---

### 9. `providers/nodes.py` (~220 lines)

**Pindah dari providers.py:**
- `GET /provider-nodes` — list_provider_nodes (lines 1761-1771)
- `POST /provider-nodes` — create_provider_node (lines 1774-1851)
- `DELETE /provider-nodes/{node_id}` — delete_provider_node (lines 1854-1881)
- `PUT /provider-nodes/{node_id}` — update_provider_node (lines 1884-1971)
- `POST /provider-nodes/validate` — validate_provider_node (lines 1998-2150)

---

## Execution Order

### Phase 1: Setup (no behavior change)
1. Buat folder `backend/app/routers/providers/`
2. Buat `__init__.py` yang re-export `router`
3. Buat `_router.py` dengan `router = APIRouter(tags=["providers"])`

### Phase 2: Extract modules (bottom-up, dependencies first)
4. `constants.py` — pindahkan constants, zero dependencies
5. `helpers.py` — pindahkan helper functions, depend on constants
6. `validation.py` — pindahkan validation functions, depend on helpers
7. `testing.py` — pindahkan test functions + endpoints, depend on validation + helpers
8. `connections.py` — pindahkan CRUD endpoints, depend on helpers + validation
9. `nodes.py` — pindahkan node endpoints, depend on helpers
10. `models.py` — pindahkan model endpoints + replace PROVIDER_MODELS_CONFIG dengan import dari `app.provider.models.config`

### Phase 3: Wire up router
11. Di `__init__.py`, import semua endpoint modules dan combine router
12. Update `backend/app/main.py` jika import path berubah
13. Delete old `backend/app/routers/providers.py`

### Phase 4: Verification
14. Run tests (jika ada)
15. Start server, test semua endpoints manual
16. Verify tidak ada import error

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Import cycle antar modules | Semua modules import dari `_router.py` dan `helpers.py`, bukan dari sesama endpoint modules |
| `main.py` import break | `__init__.py` re-exports `router` dengan path yang sama |
| `PROVIDER_MODELS_CONFIG` dipakai di tempat lain | Sudah di-verify hanya dipakai di `providers.py` |
| Route ordering (static vs parameterized) | Semua routes di-register di module masing-masing, FastAPI handle ordering by specificity |
| Lambda di `PROVIDER_MODELS_CONFIG` | Sudah di-port ke Pydantic `ProviderModelFetchConfig` di `app.provider.models.config` |

---

## Summary

| Before | After |
|--------|-------|
| 1 file, 2150 lines | 8 files, ~200-350 lines each |
| Semua tanggung jawab campur | Single Responsibility per file |
| Sulit review PR | PR per-module, mudah review |
| `PROVIDER_MODELS_CONFIG` pakai lambda | Pydantic model di `app.provider/` |
