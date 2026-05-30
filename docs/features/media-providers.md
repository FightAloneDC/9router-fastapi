# Media Providers — Architecture & API Reference

## Overview

Media Providers extend 9router's provider system with **service-kind-aware** filtering. A single provider (e.g. OpenAI) can support multiple service kinds: LLM chat, embeddings, TTS, image generation, web search, etc. The `serviceKinds` field on each provider definition controls which media tabs it appears under in the UI.

**Key design decision**: `serviceKinds` is a **frontend-only** concept. The backend stores all provider data in a flat JSON blob (`provider_connections.data`). The frontend filters and groups providers by kind using static constants.

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────┐
│  Frontend (providers.js constants)                  │
│  ┌──────────────────────────────────────────────┐   │
│  │ AI_PROVIDERS[id].serviceKinds = ["llm","tts"]│   │
│  │ MEDIA_PROVIDER_KINDS = [{id,label,icon,..}]  │   │
│  └──────────────────────────────────────────────┘   │
│                    │                                 │
│     getProvidersByKind("tts") filters AI_PROVIDERS  │
│                    │                                 │
│                    ▼                                 │
│  GET /api/providers/client  (existing endpoint)     │
│                    │                                 │
└────────────────────┼────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────┐
│  Backend           │                                 │
│                    ▼                                 │
│  provider_connections table                          │
│  ┌──────────────────────────────────────────────┐   │
│  │ id | provider | auth_type | data (JSON blob) │   │
│  │ data = { apiKey, models, baseUrl, ... }      │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### No New Backend Endpoints Needed

The existing `/api/providers` and `/api/providers/client` endpoints return all connections. Service-kind grouping is purely a frontend concern.

## The serviceKinds System

### How It Works

Each provider in `frontend/src/constants/providers.js` can declare a `serviceKinds` array. If omitted, the provider defaults to `["llm"]`.

```js
// Example: Gemini supports many service kinds
gemini: {
  id: "gemini",
  name: "Gemini",
  serviceKinds: ["llm", "embedding", "image", "imageToText", "webSearch", "tts", "stt"],
  mediaPriority: 1,  // Sort order within a kind tab
  // ...
}

// Example: Tavily is web-search only
tavily: {
  id: "tavily",
  name: "Tavily",
  serviceKinds: ["webSearch", "webFetch"],
  // ...
}

// Example: No serviceKinds → defaults to ["llm"]
ollama-local: {
  id: "ollama-local",
  name: "Ollama Local",
  // No serviceKinds → implicit ["llm"]
}
```

### Available Service Kinds

| Kind          | Label             | Endpoint                            | Description                     |
|---------------|-------------------|-------------------------------------|---------------------------------|
| `llm`         | *(default)*       | `/v1/chat/completions`              | Chat/LLM (implicit default)     |
| `embedding`   | Embedding         | `POST /v1/embeddings`               | Text embeddings                 |
| `tts`         | Text To Speech    | `POST /v1/audio/speech`             | Text-to-speech audio            |
| `stt`         | Speech To Text    | `POST /v1/audio/transcriptions`     | Speech-to-text transcription    |
| `webSearch`   | Web Search        | `POST /v1/search`                   | Web search                      |
| `webFetch`    | Web Fetch         | `POST /v1/web/fetch`                | URL content fetching            |
| `image`       | Text to Image     | `POST /v1/images/generations`       | Image generation                |
| `imageToText` | Image to Text     | `POST /v1/images/understanding`     | Image understanding/vision      |
| `video`       | Video             | `POST /v1/video/generations`        | Video generation                |
| `music`       | Music             | `POST /v1/audio/music`              | Music generation                |

These are defined in `MEDIA_PROVIDER_KINDS` in `frontend/src/constants/providers.js`.

### Provider → Kinds Mapping (from implementation)

| Provider         | serviceKinds                                          |
|------------------|-------------------------------------------------------|
| gemini           | llm, embedding, image, imageToText, webSearch, tts, stt |
| openai           | llm, embedding, tts, stt, image, imageToText, webSearch |
| azure            | llm, embedding, tts, stt, image                        |
| anthropic        | llm                                                   |
| deepseek         | llm                                                   |
| groq             | llm, stt                                              |
| mistral          | llm, embedding                                         |
| openrouter       | llm, embedding, imageToText                            |
| nvidia           | llm, tts, embedding                                    |
| together         | llm, embedding, image                                  |
| fireworks        | llm, embedding                                         |
| cohere           | llm, embedding                                         |
| cerebras         | llm                                                   |
| huggingface      | llm, embedding, image                                  |
| siliconflow      | llm, embedding, image, tts                             |
| xai              | llm, image                                            |
| minimax          | llm, image, imageToText, webSearch, tts                |
| kimi             | llm, webSearch                                         |
| tavily           | webSearch, webFetch                                    |
| brave-search     | webSearch                                             |
| serper           | webSearch                                             |
| exa              | webSearch, webFetch                                    |
| fal-ai           | image                                                |
| stability-ai     | image                                                |
| jina-ai          | embedding                                            |
| cloudflare-ai    | llm, image                                            |
| codex            | llm, image                                            |
| github           | llm, embedding                                         |

Providers without explicit `serviceKinds` (e.g. `ollama-local`, `cursor`, `kilocode`) default to `["llm"]`.

### mediaPriority

The `mediaPriority` field controls sort order within a kind tab. Lower = appears first.

```js
gemini: { mediaPriority: 1 }    // Appears first in every kind tab it belongs to
qwen:   { mediaPriority: 999 }  // Appears last (and is hidden/deprecated)
```

Default is `100` if not specified.

### Filtering Logic

```js
// From frontend/src/constants/providers.js
export function getProvidersByKind(kind) {
  return Object.values(AI_PROVIDERS)
    .filter((p) => {
      const kinds = p.serviceKinds ?? ["llm"];  // Default to ["llm"]
      if (!kinds.includes(kind)) return false;
      if (p.hidden) return false;               // Skip hidden providers
      return true;
    })
    .sort((a, b) => (a.mediaPriority ?? 100) - (b.mediaPriority ?? 100));
}
```

## The Model Type System

### Backend Model Storage

Models are stored as a simple string array in the connection's JSON data blob:

```json
{
  "apiKey": "sk-...",
  "baseUrl": "https://api.openai.com/v1",
  "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
  "roundRobin": false,
  "testStatus": "connected"
}
```

### Model Fetching

The backend has per-provider model fetching configs in `backend/app/routers/providers/models.py`. Each provider knows how to:
1. Call the upstream `/models` endpoint
2. Parse the response into a normalized `[{id, name}]` format
3. Store the model IDs in the connection's `data.models` field

**Endpoint**: `GET /api/providers/{conn_id}/models`

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/providers/<conn_id>/models
```

**Response**:
```json
{
  "provider": "openai",
  "connectionId": "uuid-here",
  "models": [
    {"id": "gpt-4o", "name": "gpt-4o"},
    {"id": "gpt-4o-mini", "name": "gpt-4o-mini"}
  ]
}
```

### Model Normalization

All model responses are normalized to `{id, name}` format:

```python
def _normalize_model(m):
    if isinstance(m, str):
        return {"id": m, "name": m}
    return {
        "id": m.get("id") or m.get("name") or m.get("model", ""),
        "name": m.get("name") or m.get("display_name") or m.get("displayName") or m.get("id", ""),
    }
```

### Compatible Provider Nodes

Custom OpenAI/Anthropic-compatible endpoints are stored as `ProviderNode` records:

```python
class ProviderNode(Base):
    __tablename__ = "provider_nodes"
    id: str        # e.g. "openai-compatible-myserver"
    type: str      # "openai-compatible" | "anthropic-compatible" | "custom-embedding"
    name: str      # Display name
    data: str      # JSON: {baseUrl, prefix, apiType}
```

Node types:
- `openai-compatible` — Uses `Authorization: Bearer <key>` + `GET /models`
- `anthropic-compatible` — Uses `x-api-key: <key>` + `anthropic-version` header + `GET /models`
- `custom-embedding` — Custom embedding endpoint

## API Reference

### Provider Connections

| Method   | Path                              | Auth   | Description                              |
|----------|-----------------------------------|--------|------------------------------------------|
| `GET`    | `/api/providers`                  | Yes    | List all connections (full, no secrets)  |
| `GET`    | `/api/providers/client`           | Yes    | List connections (sanitized for UI)      |
| `POST`   | `/api/providers`                  | Yes    | Create a new connection                  |
| `GET`    | `/api/providers/{conn_id}`        | Yes    | Get single connection                    |
| `PATCH`  | `/api/providers/{conn_id}`        | Yes    | Update connection                        |
| `DELETE` | `/api/providers/{conn_id}`        | Yes    | Delete connection                        |
| `POST`   | `/api/providers/{conn_id}/test`   | Yes    | Test connection (lightweight API call)   |
| `GET`    | `/api/providers/{conn_id}/models` | Yes    | Fetch models from upstream provider      |
| `DELETE` | `/api/providers/{conn_id}/models` | Yes    | Clear cached models                      |

### Provider Validation & Testing

| Method | Path                          | Auth | Description                              |
|--------|-------------------------------|------|------------------------------------------|
| `POST` | `/api/providers/validate`     | Yes  | Validate credentials (pre-create check) |
| `POST` | `/api/providers/test-batch`   | Yes  | Batch test connections by group          |

### Suggested Models

| Method | Path                              | Auth | Description                              |
|--------|-----------------------------------|------|------------------------------------------|
| `GET`  | `/api/providers/suggested-models` | Yes  | Fetch/filter suggested models            |

Query params: `url` (models endpoint URL), `type` (filter: `openrouter-free`, `opencode-free`, `kilo-gateway`)

### Provider Nodes (Custom Compatible Providers)

| Method   | Path                            | Auth | Description                              |
|----------|---------------------------------|------|------------------------------------------|
| `GET`    | `/api/provider-nodes`           | Yes  | List all custom provider nodes           |
| `POST`   | `/api/provider-nodes`           | Yes  | Create a custom provider node            |
| `PUT`    | `/api/provider-nodes/{id}`      | Yes  | Update a custom provider node            |
| `DELETE` | `/api/provider-nodes/{id}`      | Yes  | Delete a custom provider node            |
| `POST`   | `/api/provider-nodes/validate`  | Yes  | Validate a node's API key                |

### Model Management

| Method   | Path                          | Auth | Description                              |
|----------|-------------------------------|------|------------------------------------------|
| `GET`    | `/api/models/alias`           | Yes  | List model aliases                       |
| `PUT`    | `/api/models/alias`           | Yes  | Set a model alias                        |
| `DELETE` | `/api/models/alias`           | Yes  | Delete a model alias                     |
| `GET`    | `/api/models/custom`          | Yes  | List custom models                       |
| `POST`   | `/api/models/custom`          | Yes  | Add a custom model                       |
| `DELETE` | `/api/models/custom`          | Yes  | Delete a custom model                    |
| `GET`    | `/api/models/disabled`        | Yes  | List disabled models                     |
| `POST`   | `/api/models/disabled`        | Yes  | Disable models                           |
| `DELETE` | `/api/models/disabled`        | Yes  | Enable (un-disable) models               |
| `GET`    | `/api/models/availability`    | Yes  | Get model availability/cooldown status   |
| `POST`   | `/api/models/availability`    | Yes  | Clear model cooldown                     |
| `POST`   | `/api/models/test`            | Yes  | Test a specific model                    |

## Data Schemas

### ProviderConnectionCreate

```json
{
  "provider": "openai",
  "name": "My OpenAI Key",
  "displayName": "Production OpenAI",
  "apiKey": "sk-...",
  "auth_type": "apikey",
  "priority": 1,
  "globalPriority": null,
  "defaultModel": "gpt-4o",
  "models": ["gpt-4o", "gpt-4o-mini"],
  "round_robin": false,
  "baseUrl": null,
  "proxyPoolId": null,
  "testStatus": null,
  "providerSpecificData": null,
  "connectionProxyEnabled": false,
  "connectionProxyUrl": "",
  "connectionNoProxy": ""
}
```

### ProviderConnectionOut

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "provider": "openai",
  "auth_type": "apikey",
  "name": "My OpenAI Key",
  "email": null,
  "displayName": "Production OpenAI",
  "priority": 1,
  "globalPriority": null,
  "is_active": true,
  "defaultModel": "gpt-4o",
  "test_status": "connected",
  "lastError": null,
  "lastErrorAt": null,
  "errorCode": null,
  "expiresAt": null,
  "lastUsedAt": null,
  "consecutiveUseCount": null,
  "models": ["gpt-4o", "gpt-4o-mini"],
  "round_robin": false,
  "base_url": "https://api.openai.com/v1",
  "proxy_pool_id": null,
  "providerSpecificData": null,
  "created_at": "2026-05-21T10:00:00Z",
  "updated_at": "2026-05-21T10:00:00Z"
}
```

### ProviderTestResponse

```json
{
  "valid": true,
  "error": null,
  "refreshed": false,
  "latencyMs": 234,
  "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
}
```

### BatchTestRequest / BatchTestResponse

```json
// Request
{
  "mode": "all",           // "provider" | "apikey" | "all"
  "providerId": null       // Required when mode="provider"
}

// Response
{
  "mode": "all",
  "providerId": null,
  "results": [
    {
      "provider": "openai",
      "connectionId": "uuid",
      "connectionName": "My OpenAI Key",
      "authType": "apikey",
      "valid": true,
      "latencyMs": 234,
      "error": null,
      "testedAt": "2026-05-21T10:00:00Z"
    }
  ],
  "summary": {"total": 5, "passed": 4, "failed": 1},
  "testedAt": "2026-05-21T10:00:00Z"
}
```

## How to Add a New Provider with serviceKinds

### Step 1: Add Provider Defaults (Backend)

In `backend/app/routers/providers/constants.py`, add to `PROVIDER_DEFAULTS`:

```python
"my-provider": {"baseUrl": "https://api.myprovider.com/v1", "validationType": "openai"},
```

### Step 2: Add Model Fetching Config (Backend)

In `backend/app/routers/providers/models.py`, add to `PROVIDER_MODELS_CONFIG`:

```python
"my-provider": {
    "url": "https://api.myprovider.com/v1/models",
    "method": "GET",
    "headers": {"Content-Type": "application/json"},
    "authHeader": "Authorization",
    "authPrefix": "Bearer ",
    "parseResponse": lambda data: data.get("data", []),
},
```

### Step 3: Add Provider Definition (Frontend)

In `frontend/src/constants/providers.js`, add to the appropriate category:

```js
// In APIKEY_PROVIDERS (or FREE_TIER_PROVIDERS, etc.)
"my-provider": {
  id: "my-provider",
  alias: "mp",
  name: "My Provider",
  icon: "Sparkles",
  color: "#FF6B35",
  textIcon: "MP",
  website: "https://myprovider.com",
  notice: { apiKeyUrl: "https://myprovider.com/api-keys" },
  serviceKinds: ["llm", "embedding", "image"],  // <-- Which media tabs it appears in
},
```

### Step 4: That's It

No other changes needed. The frontend's `getProvidersByKind()` will automatically include this provider in the Embedding and Image media tabs. The backend handles model fetching and connection testing via the existing generic infrastructure.

## Frontend Routes

```
/media-providers                    → MediaProvidersPage (default: embedding tab)
/media-providers/:kind              → MediaProvidersPage (active tab = kind)
/media-providers/:kind/:providerId  → MediaProviderDetailPage
```

## Key Files

| File | Purpose |
|------|---------|
| `frontend/src/constants/providers.js` | Provider definitions, serviceKinds, MEDIA_PROVIDER_KINDS, getProvidersByKind() |
| `backend/app/routers/providers/constants.py` | PROVIDER_DEFAULTS (base URLs, validation types) |
| `backend/app/routers/providers/models.py` | Per-provider model fetching configs + fetch endpoint |
| `backend/app/routers/providers/connections.py` | CRUD endpoints for provider connections |
| `backend/app/routers/providers/testing.py` | Connection testing + batch test endpoints |
| `backend/app/routers/providers/helpers.py` | Data conversion, proxy config, model normalization |
| `backend/app/routers/providers/validation.py` | Per-validation-type credential checks |
| `backend/app/schemas/provider.py` | Pydantic request/response schemas |
| `backend/app/models/provider.py` | SQLAlchemy models (ProviderConnection, ProviderNode) |
| `frontend/src/api/providers.js` | Frontend API client for all provider endpoints |
