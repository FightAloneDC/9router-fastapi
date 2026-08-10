# Plan: Add Proxy Reranker Support Feature

**Date**: 2026-08-10
**Status**: Active plan
**Project**: 9Router FastAPI
**Related**: Search proxy feature (`/v1/search`), Embeddings proxy (`/v1/embeddings`)

## Overview

Add support for reranking (search re-ranking) through a proxy endpoint, following the existing PS (Provider-Specific) architecture used for providers like Tavily, Brave, and Cohere.

## Goals

1. Create `/v1/rerank` endpoint similar to `/v1/search`
2. Implement PS-pattern handler system for provider-specific rerank implementations
3. Support multiple rerank providers (Cohere, Jina AI, SiliconFlow, Voyage AI, Alibaba, etc.)
4. Integrate with existing auth, usage tracking, and fallback mechanisms
5. Provide unified response format across all rerank providers
6. Document template for new providers — separate PR if needed

## Architecture Overview

```
/v1/rerank (new endpoint)
    ↓
execute_rerank() [in services/rerank_adapters.py]
    ↓
dispatches to provider handler (PS pattern)
    ↓
ProviderHandler.execute_rerank() [per-provider]
    ↓
Unifies response → save_request_tracking → return
```

## Implementation Steps

### Phase 1: Backend Infrastructure

#### 1.1 Create Rerank Adapters Service
**File**: `backend/app/services/rerank_adapters.py`

Create dispatcher that:
- Accepts provider_id, query, documents, params
- Dispatches to provider handler's `execute_rerank()` method
- Returns unified rerank result format

Structure:
```python
async def execute_rerank(
    client: httpx.AsyncClient,
    provider_id: str,
    params: dict,
    token: str,
    provider_data: dict | None = None,
) -> dict:
    """Execute rerank request and return normalized results."""
```

Unified response schema:
```json
{
  "provider": "cohere",
  "query": "search query here",
  "results": [
    {
      "index": 0,
      "document": {"text": "..."},
      "relevance_score": 0.95,
      "rank": 1
    }
  ],
  "usage": {"queries_used": 1},
  "metrics": {},
  "errors": []
}
```

#### 1.2 Create Rerank Endpoint Router
**File**: `backend/app/routers/v1_proxy/rerank.py`

Implement POST /v1/rerank endpoint:
- Request body validation
- Model/provider resolution via `_resolve_provider_alias()`
- Connection lookup from `ProviderConnection` table
- Auth handling (API key from connection data)
- Error handling with proper HTTP codes
- Usage tracking via `save_request_tracking()`

Key fields accepted:
- `model` or `provider`: rerank provider ID
- `query`: search query string (required)
- `documents`: array of document strings or objects (required)
- `top_n`: max results (default 10, max 100)
- `return_documents`: boolean (include doc text in response)
- `language`: optional language code
- `provider_options`: provider-specific options

#### 1.3 Register Router in Main Application
**File**: `backend/app/routers/v1_proxy/router.py`

Add import and include_router:
```python
from .rerank import router as rerank_router
router.include_router(rerank_router)
```

#### 1.4 Update Proxy Service (if needed)
**File**: `backend/app/services/proxy.py`

Check if any updates needed:
- Add `SERVICE_KINDS = ["rerank"]` to base config? (optional, can be per-provider)
- Ensure alias resolution works for new providers

### Phase 2: Provider Handlers (PS Pattern)

For each supported rerank provider, create/update handler in `backend/app/providers/<provider>/handler.py`

#### 2.1 Cohere Handler
**Provider**: `backend/app/providers/cohere/`

Update `handler.py` (create if missing):
```python
class CohereHandler(BaseProviderHandler):
    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Cohere rerank API: POST /rerank"""
        # Build request
        # Call Cohere rerank endpoint
        # Normalize results to unified schema
```

Config update `config.py`:
```python
SERVICE_KINDS: list[str] = ["llm", "embedding", "rerank"]
```
Note: Cohere rerank uses the native API base (`https://api.cohere.com/v1`), not the `/compatibility/v1` base — resolve per-endpoint in the handler.

#### 2.2 Jina AI Handler
**Provider**: `backend/app/providers/jina_ai/`

Update `handler.py` (create if missing):
```python
class JinaAiHandler(BaseProviderHandler):
    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Jina AI Rerank: POST /v1/rerank"""
```

Config update `config.py`:
```python
SERVICE_KINDS: list[str] = ["embedding", "rerank"]
```

#### 2.3 SiliconFlow Handler
**Provider**: `backend/app/providers/siliconflow/`

Add `execute_rerank()` method to existing handler (`SiliconflowHandler`).

#### 2.4 Voyage AI Handler
**Provider**: `backend/app/providers/voyage_ai/`

Update `config.py`:
```python
SERVICE_KINDS: list[str] = ["embedding", "rerank"]
```

Create/update `handler.py` with `execute_rerank()` method:
```python
class VoyageAiHandler(BaseProviderHandler):
    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Voyage AI Rerank: POST /v1/rerank"""
        # Build request
        # Call Voyage rerank endpoint
        # Normalize results to unified schema
```

Note: Voyage AI has strong rerank models (e.g., `rerank-lite-1`, `rerank-1`) — ideal candidate for this feature.

#### 2.5 Alibaba DashScope Handlers

**Providers**: `backend/app/providers/alims_intl/`, `alicode/`, `alicode_intl/`

All three variants already exist with basic LLM support. Need to add rerank capability based on [DashScope Text Rerank API](https://www.alibabacloud.com/help/en/model-studio/text-rerank-api?spm=a2c63.p38356.0.i1).

##### 2.5.1 `alims-intl` (Alibaba Studio / Model Studio Intl)

**Config update** (`config.py`):
```python
SERVICE_KINDS: list[str] = ["llm", "rerank"]
```

**Handler update** (`handler.py` - existing file):
Add `execute_rerank()` method to `AlimsIntlHandler`:

```python
class AlimsIntlHandler(BaseProviderHandler):
    # ... existing prepare_request method ...
    
    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """DashScope Rerank API via MAAS (Model-as-a-Service).
        
        Reference: https://www.alibabacloud.com/help/en/model-studio/text-rerank-api
        
        Supports qwen3-rerank and gte-rerank-v2 models.
        Regional endpoints differ by workspace ID:
          - China (Beijing): https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
          - Singapore: https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
          - EU Frankfurt: https://{WorkspaceId}.eu-central-1.maas.aliyuncs.com/compatible-mode/v1
          
        For qwen3-rerank without workspace routing, use compatible-mode endpoints:
          - Beijing: POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-api/v1/reranks
          - Singapore: POST https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/reranks
        """
        query = params["query"]
        documents = params["documents"]
        top_n = params.get("top_n", 10)
        return_documents = params.get("return_documents", False)
        instruct = params.get("instruct")
        
        base_url = self._resolve_base_url(provider_data or {})
        
        # Build request body for qwen3-rerank format (flat structure)
        body: dict = {
            "model": params.get("model", "qwen3-rerank"),
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        if instruct:
            body["instruct"] = instruct
        
        url = f"{base_url.rstrip('/')}/compatible-mode/v1/reranks"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        
        data = resp.json()
        
        # Normalize response to unified schema
        results = []
        for r in data.get("results", []):
            result_item = {
                "index": r["index"],
                "relevance_score": r["relevance_score"],
            }
            if return_documents and "document" in r:
                result_item["document"] = r["document"]
            results.append(result_item)
        
        return {
            "results": results,
            "usage": {"total_tokens": data.get("usage", {}).get("total_tokens", 0)},
            "metrics": {"request_id": data.get("id", data.get("request_id"))},
        }
```

**Key details from DashScope documentation:**

**Supported Models:**
| Model | Max Docs | Max Tokens/doc | Total Tokens | Languages | Endpoint Format |
|-------|----------|----------------|--------------|-----------|-----------------|
| **qwen3-rerank** (recommended) | 500 | 4,000 | 120,000 | 100+ languages | `/compatible-api/v1/reranks` |
| qwen3-vl-rerank | 100 text + 40 img + 48 video | 4,000 text | 120,000 | 33 langs | `/api/v1/services/rerank/text-rerank/` |
| gte-rerank-v2 | 500 | 4,000 | 30,000 | 50+ langs | `/api/v1/services/rerank/text-rerank/` |

**Request Body Structure (qwen3-rerank):**
```json
{
  "model": "qwen3-rerank",
  "query": "What is a rerank model?",
  "documents": [...],
  "top_n": 10,
  "instruct": "Given a web search query, retrieve relevant passages..."
}
```

**Response Format (normalized from DashScope):**
```json
{
  "object": "list",
  "results": [
    {"index": 0, "relevance_score": 0.9334521178273196},
    {"index": 2, "relevance_score": 0.34100082626411193}
  ],
  "model": "qwen3-rerank",
  "id": "85ba5752-1900-47d2-8896-23f99b13f6e1",
  "usage": {"total_tokens": 79}
}
```

**Important Notes:**
- Uses **Bearer token auth** (`sk-xxx` standard DashScope keys)
- Supports bulk import via farm-json (from existing `bulk.py`)
- Requires **workspace-specific regional endpoints** — resolve base URL from `provider_data` or connection config
- The `instruct` parameter guides re-ranking behavior (default: Q&A retrieval task)
- `gte-rerank-v2` will be deprecated May 30, 2026 — migrate to `qwen3-rerank`

##### 2.5.2 `alicode` & `alicode-intl` (Alibaba Coding Plan)

These providers need handler files created. Use similar implementation as `alims-intl` but different base URLs:

**Create `alicode/handler.py`:**
```python
from app.providers.alicode.config import AlicodeConfig
from app.providers.base import BaseProviderHandler


class AlicodeHandler(BaseProviderHandler):
    """Handle Qwen rerank requests for Alibaba Coding Plan."""
    
    async def execute_rerank(self, client, *, token, params, provider_data=None):
        """Qwen Rerank: POST /v1/reranks via coding.dashscope.aliyuncs.com"""
        # Same logic as alims-intl, just different BASE_URL
        # Base URL: https://coding.dashscope.aliyuncs.com/v1
```

**Create `alicode_intl/handler.py`:**
```python
from app.providers.alicode_intl.config import AlicodeIntlConfig
from app.providers.base import BaseProviderHandler


class AlicodeIntlHandler(BaseProviderHandler):
    """Handle Qwen rerank for international Coding Plan."""
    
    async def execute_rerank(self, client, *, token, params, provider_data=None):
        """Qwen Rerank: POST /v1/reranks via coding-intl.dashscope.aliyuncs.com"""
        # Same logic as alims-intl, just different BASE_URL
        # Base URL: https://coding-intl.dashscope.aliyuncs.com/v1
```

**Config updates:**
```python
# alicode/config.py
SERVICE_KINDS: list[str] = ["llm", "rerank"]

# alicode_intl/config.py  
SERVICE_KINDS: list[str] = ["llm", "rerank"]
```

**Use cases:**
- `alims-intl`: International users, full feature set (bulk import, multi-region)
- `alicode`: Domestic Chinese market, simpler setup
- `alicode-intl`: Global customers outside China

Update all three configs to include rerank models in their model lists too.

#### 2.6 New Provider Templates
Create template for adding new rerank providers:
```bash
mkdir -p backend/app/providers/{provider-name}/
touch backend/app/providers/{provider-name}/__init__.py
```

Template files:
- `config.py`: Identity, metadata, service_kinds
- `handler.py`: execute_rerank implementation
- `models.py`: Optional model parsing (if applicable)
- `constants.py`: Optional constants

### Phase 3: Frontend Integration (Optional but Recommended)

#### 3.1 API Client Module
**File**: `frontend/src/api/rerank.js`

```javascript
export async function rerank(data) {
  return axios.post('/v1/rerank', data);
}

export async function getAvailableRerankProviders() {
  const catalog = useCatalogStore.getState().catalog;
  return catalog.filter(p => p.serviceKinds?.includes('rerank'));
}
```

#### 3.2 UI Components (Optional)

- `src/components/RerankModal.jsx`: Modal for testing rerank configuration
- `src/pages/RerankPage.jsx`: Full page view for rerank operations
- Add rerank option to Providers menu dropdown

#### 3.3 Catalog Store Updates
**File**: `frontend/src/stores/catalogStore.js`

Ensure catalog includes `serviceKinds` field and filters by "rerank".

### Phase 4: Testing & Validation

#### 4.1 Unit Tests
**Location**: `tests/unit/test_rerank*`

Test cases:
- Parameter validation
- Provider dispatching
- Response normalization
- Error handling

#### 4.2 Integration Tests
**Location**: `tests/integration/test_rerank*`

Test real providers:
- Cohere rerank integration
- Jina AI rerank integration
- Timeout/connection error handling

#### 4.3 Manual Testing Checklist

1. POST /v1/rerank with valid provider + query + docs
2. Test different top_n values (1-100)
3. Test return_documents=true/false
4. Test invalid provider → 501 Not Implemented
5. Test missing required fields → 400 Bad Request
6. Test connection timeout → 503 Service Unavailable
7. Verify usage tracking in DB
8. Test fallback on error

### Phase 5: Documentation

#### 5.1 API Documentation
**File**: `docs/reference/rerank-api.md`

Document:
- Endpoint specification
- Request/response schema
- Supported providers
- Error codes
- Examples

#### 5.2 Developer Guide
**File**: `docs/development/add-rerank-provider.md`

Guide for adding new rerank providers:
- PS pattern recap
- Required files
- Handler implementation checklist
- Testing guidelines

## Trade-offs Considered

### Approach 1: Standalone Rerank Endpoint (Selected)
- **Pros**: Clean separation from search, follows OpenAI convention, easier to maintain
- **Cons**: More endpoints to manage

### Approach 2: Combined Search+Rerank Endpoint
- **Pros**: Fewer endpoints, single request flow
- **Cons**: More complex, harder to maintain, deviates from standard patterns

**Chosen**: Approach 1 — separate endpoints follow established patterns better.

### Approach 3: Hybrid (Rerank within Search)
- Could add optional `rerank: true` param to search endpoint
- **Decision**: Keep separate for now; can add hybrid later if needed

## Dependencies

### External Services (Examples)
| Provider | Base URL | Auth | Pricing | Rerank Models |
|----------|----------|------|---------|---------------|
| Cohere | https://api.cohere.com/v1 | Bearer | Paid tier | rerank-5, rerank-lite-1 |
| Jina AI | https://api.jina.ai/v1 | Bearer | Free tier available | jina-reranker-v1, jina-colbert-v1 |
| SiliconFlow | Custom | Bearer | Usage-based | Various Qwen reranks |
| Voyage AI | https://api.voyageai.com/v1 | Bearer | Free tier + paid tiers | rerank-lite-1, rerank-1 |
| **Alibaba (alims-intl)** | `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` | Bearer (sk-...) | Competitive pricing | qwen3-rerank, qwen3-vl-rerank, gte-rerank-v2 |
| **Alibaba (alicode/intl)** | `coding.dashscope.aliyuncs.com` / `coding-intl...` | Bearer | Cost-effective | Model Studio platform |

**DashScope Rerank Models** (from [Text Rerank API docs](https://www.alibabacloud.com/help/en/model-studio/text-rerank-api)):
| Model | Max Docs | Max Tokens/doc | Notes |
|-------|----------|----------------|-------|
| **qwen3-rerank** | 500 | 4,000 | Latest, 100+ languages, recommended |
| qwen3-vl-rerank | 100 text + 40 img + 48 video | 4,000 text | Multimodal, 33 languages |
| gte-rerank-v2 | 500 | 4,000 | Legacy, deprecated May 2026 |

**Note on DashScope**: All 3 Alibaba variants support DashScope platform:
- `alims-intl`: Model Studio Intl — standard DashScope keys (sk-...), supports bulk import via farm-json
- `alicode`: Alibaba Coding Plan — for domestic Chinese users
- `alicode-intl`: International Coding Plan — for global customers
- Workspace-specific regional endpoints required (Beijing/Singapore/Frankfurt)

### Internal Dependencies
- Existing authentication system (`validate_api_key`)
- Usage tracking service (`save_request_tracking`)
- Proxy routing infrastructure (`services/proxy.py`)
- Provider catalog system (`/providers/catalog`)

## Success Criteria

1. POST /v1/rerank endpoint functional
2. At least 3 working providers (Cohere + Jina AI + Voyage AI recommended minimum)
3. **Alibaba DashScope support** — all 3 variants (alims-intl, alicode, alicode-intl) documented and ready for implementation
4. Unified response format across providers
5. Proper error handling (400, 401, 403, 404, 429, 503)
6. Usage tracked in database
7. Tests passing (unit + integration)

## Estimated Complexity

- **Backend**: Medium (~5-7 hours for core implementation + 3+ providers)
  - Core infra: ~3-4 hours
  - Cohere/Jina AI/Voyage: ~2-3 hours
  - **Alibaba (3 variants)**: optional add-on, ~1-2 hours extra if needed
- **Frontend**: Low-Medium (~2-3 hours for basic integration)
- **Testing**: Medium (~2 hours for unit + integration tests)
- **Documentation**: Low (~1 hour)

**Total estimated time**: 9-14 hours (without Alibaba), **10-15 hours with full Alibaba support**

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Provider API changes | Low | Medium | Abstract behind handler interface |
| Rate limiting | Medium | Medium | Implement proper backoff/retry logic |
| Schema incompatibility | Medium | Medium | Robust normalization layer in adapter |
| Security vulnerabilities | Low | High | Follow existing auth patterns strictly |

## Future Enhancements (Not in Scope)

1. Batch rerank processing (multiple queries at once)
2. Rerank caching (Redis/Memcached)
3. Multi-stage pipelines (fetch → rerank → filter)
4. Local/on-premise rerankers (LLM-powered)
5. A/B testing between rerank providers
6. Additional provider integrations (beyond DashScope variants)
