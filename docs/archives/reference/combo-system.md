# Combo System Documentation

## Apa itu Combo?

Combo adalah **named group of models** yang bisa dipakai sebagai 1 model name. User kirim request dengan nama combo, proxy expand ke beberapa model dan apply rotation/fallback strategy.

## Contoh

### Definisi Combo (di DB)
```
Combo "fast-llm" → models: ["openai/gpt-4o-mini", "anthropic/claude-haiku", "gemini/gemini-flash"]
Combo "smart-llm" → models: ["openai/gpt-4o", "anthropic/claude-opus"]
Combo "free-llm" → models: ["groq/llama-3", "cerebras/llama-3"]
```

### Request
```json
POST /v1/chat/completions
{
  "model": "fast-llm",
  "messages": [{"role": "user", "content": "hi"}]
}
```

### Proxy Flow
```
1. Cek "fast-llm" → match combo di DB
2. Expand ke models: ["openai/gpt-4o-mini", "anthropic/claude-haiku", "gemini/gemini-flash"]
3. Apply combo strategy (fallback/round-robin)
4. Loop through models:
   - Try "openai/gpt-4o-mini" → gagal (429)
   - Try "anthropic/claude-haiku" → sukses!
   - Return response
```

---

## Dua Level Rotation

### Level 1: Combo Rotation (Cross-Provider)

Menentukan **model mana yang dicoba duluan**.

```
Combo "fast-llm" dengan 3 models:

Strategy "fallback":
  Selalu coba urutan: gpt-4o-mini → claude-haiku → gemini-flash

Strategy "round-robin" (sticky=2):
  Request 1,2: gpt-4o-mini → claude-haiku → gemini-flash
  Request 3,4: claude-haiku → gemini-flash → gpt-4o-mini
  Request 5,6: gemini-flash → gpt-4o-mini → claude-haiku
```

### Level 2: Connection Rotation (Within-Provider)

Menentukan **API key mana yang dipakai** untuk 1 provider.

```
Provider "anthropic" punya 3 connections: key-A, key-B, key-C

Strategy "fill-first":
  Selalu pakai key-A (priority tertinggi)

Strategy "round-robin" (sticky=3):
  Request 1,2,3: key-A
  Request 4,5,6: key-B
  Request 7,8,9: key-C
  Request 10,11,12: key-A (wrap around)
```

### Flow Lengkap
```
Request "fast-llm"
  → Combo round-robin → coba "claude-haiku" dulu
    → Provider "anthropic" punya 3 connections
    → Connection round-robin → pakai key-B
      → Request ke Anthropic dengan key-B
      → Gagal (429) → cooldown key-B
      → Fallback → pakai key-C
      → Sukses! Return response
```

---

## Struktur Data (dari DB asli)

### Combo Table
```sql
CREATE TABLE combos (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,     -- "honcho-dialectic-minimal"
    kind TEXT,                     -- null atau "llm", "tts", dll
    models TEXT NOT NULL,          -- JSON array: ["samba/gemma-3-12b-it", "xmtp/mimo-v2.5"]
    createdAt TEXT,
    updatedAt TEXT
);
```

**Contoh data asli:**
```
Combo "honcho-dialectic-minimal" → ["samba/gemma-3-12b-it", "openrouter/openrouter/owl-alpha", "xmtp/mimo-v2.5"]
Combo "honcho-dialectic-max" → ["kr/claude-haiku-4.5", "mimo/mimo-v2.5-pro", "xmtp/mimo-v2.5-pro"]
```

### Settings (JSON blob, id=1)
```json
{
  "comboStrategy": "round-robin",
  "providerStrategies": {
    "kiro": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1},
    "kilocode": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1},
    "nvidia": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1},
    "openrouter": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1},
    "gemini": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1},
    "cerebras": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1},
    "xiaomi-mimo": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1},
    "xiaomi-tokenplan": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1}
  },
  "comboStrategies": {
    "honcho-dialectic-minimal": {"fallbackStrategy": "round-robin"},
    "honcho-dialectic-max": {"fallbackStrategy": "round-robin"},
    "claude-opus-4-7": {"fallbackStrategy": "round-robin"}
  },
  "password": "...",
  "requireApiKey": true
}
```

**Catatan:** Tidak ada `fallbackStrategy` global atau `stickyRoundRobinLimit` global di settings asli. Semua per-provider.

### ProviderConnection (JSON data blob)
```json
{
  "apiKey": "...",
  "lastUsedAt": "2026-05-27T19:57:50.389Z",
  "consecutiveUseCount": 1,
  "backoffLevel": 0,
  "testStatus": "active",
  "modelLock_mimo-v2.5": null,
  "modelLock_mimo-v2-pro": "2026-05-27T20:02:01.422Z",
  "modelLock_mimo-v2-omni": null
}
```

**Contoh connection dengan cooldown:**
```json
{
  "lastUsedAt": "2026-05-27T19:57:00.552Z",
  "consecutiveUseCount": 1,
  "backoffLevel": 10,
  "testStatus": "unavailable",
  "modelLock_mimo-v2.5": "2026-05-27T19:41:55.765Z",
  "modelLock_mimo-v2-pro": "2026-05-27T20:02:01.422Z"
}
```

---

## Original Node.js Reference

### Combo Rotation (`open-sse/services/combo.js`)

```javascript
// In-memory rotation state per combo
const comboRotationState = new Map();

export function getRotatedModels(models, comboName, strategy, stickyLimit = 1) {
  if (!models || models.length <= 1 || strategy !== "round-robin") {
    return models;
  }
  
  const state = comboRotationState.get(comboName) || { index: 0, consecutiveUseCount: 0 };
  const currentIndex = state.index % models.length;
  const rotatedModels = rotateModelsFromIndex(models, currentIndex);
  
  // Update state
  const nextUseCount = state.consecutiveUseCount + 1;
  if (nextUseCount >= stickyLimit) {
    comboRotationState.set(comboName, {
      index: (currentIndex + 1) % models.length,
      consecutiveUseCount: 0
    });
  } else {
    comboRotationState.set(comboName, {
      index: currentIndex,
      consecutiveUseCount: nextUseCount
    });
  }
  
  return rotatedModels;
}
```

### Combo Fallback (`open-sse/services/combo.js`)

```javascript
export async function handleComboChat({ body, models, handleSingleModel, comboName, comboStrategy, comboStickyLimit }) {
  const rotatedModels = getRotatedModels(models, comboName, comboStrategy, comboStickyLimit);
  
  for (const modelStr of rotatedModels) {
    try {
      const result = await handleSingleModel(body, modelStr);
      if (result.ok) return result;
      
      // Check if should fallback
      const { shouldFallback } = checkFallbackError(result.status, errorText);
      if (!shouldFallback) return result;
      
      // Try next model
    } catch (error) {
      // Continue to next model
    }
  }
  
  // All models failed
  return errorResponse(503, "All combo models unavailable");
}
```

### Connection Selection (`src/sse/services/auth.js`)

```javascript
export async function getProviderCredentials(provider, excludeConnectionIds, model) {
  const connections = await getProviderConnections({ provider, isActive: true });
  
  // Filter out excluded and model-locked
  const available = connections.filter(c => {
    if (excludeSet.has(c.id)) return false;
    if (isModelLockActive(c, model)) return false;
    return true;
  });
  
  // Get strategy
  const providerOverride = settings.providerStrategies[providerId] || {};
  const strategy = providerOverride.fallbackStrategy || settings.fallbackStrategy || "fill-first";
  
  let connection;
  if (strategy === "round-robin") {
    const stickyLimit = providerOverride.stickyRoundRobinLimit || settings.stickyRoundRobinLimit || 3;
    
    // Sort by lastUsedAt (most recent first)
    const byRecency = [...available].sort((a, b) => new Date(b.lastUsedAt) - new Date(a.lastUsedAt));
    const current = byRecency[0];
    
    if (current.lastUsedAt && current.consecutiveUseCount < stickyLimit) {
      // Stay with current
      connection = current;
      await updateConnection(connection.id, {
        lastUsedAt: new Date().toISOString(),
        consecutiveUseCount: current.consecutiveUseCount + 1
      });
    } else {
      // Pick least recently used
      const byOldest = [...available].sort((a, b) => new Date(a.lastUsedAt) - new Date(b.lastUsedAt));
      connection = byOldest[0];
      await updateConnection(connection.id, {
        lastUsedAt: new Date().toISOString(),
        consecutiveUseCount: 1
      });
    }
  } else {
    // fill-first (default)
    connection = available[0];
  }
  
  return connection;
}
```

---

## FastAPI Current State

### Yang Sudah Ada

**Combo & Rotation:**
- Combo table di DB (`app/models/combo.py`)
- `get_rotated_targets()` — combo rotation dengan `round-robin` (random jitter anti-ban) dan `random` strategies
- `select_connection_for_provider()` — connection selection dengan 3 strategies: `fill-first`, `round-robin`, `random`
- Per-combo strategy override via `get_combo_strategy()` (comboStrategies di settings)
- Per-provider strategy override via `get_provider_strategy()` (providerStrategies di settings)
- `stickyRoundRobinLimit` per-provider dan per-combo

**Connection Selection & Caching:**
- `get_connections_cached()` — in-memory cache dengan 30s TTL, avoids DB query per request
- `invalidate_connection_cache()` — cache invalidation on error/success
- `reset_connection_rotation()` — reset rotation state when connections change

**Cooldown & Error Handling:**
- `ERROR_RULES` — text-based dan status-based error matching (401/402/403/404/429, 5xx)
- `calculate_cooldown()` — exponential backoff (base 2s, max 5min, 15 levels)
- `mark_connection_unavailable()` — write cooldown + backoffLevel + testStatus ke DB
- `clear_connection_error()` — clear cooldown on success, set testStatus=active
- `is_rate_limited()` — check `rateLimitedUntil` in connection data
- `build_cooldown_update()` / `build_clear_cooldown_update()` — update builders

**Model Lock:**
- `is_model_lock_active()` — check `modelLock_<model>` field di connection data
- `build_cooldown_update()` — sets model lock on error
- `clear_connection_error()` — clears expired model locks on success

**Fallback Loop:**
- `while True` loop di semua endpoints (chat/completions, messages, embeddings, audio/speech, audio/transcriptions, images/generations, responses)
- `exclude_ids: set[str]` — failed connection IDs excluded from retry
- Cooldown on error + clear on success di setiap loop iteration
- `should_fallback_on_error()` — determines if error triggers fallback (5xx, 429, 401-404, text-matched)

**Observability:**
- `update_connection_usage()` — writes `lastUsedAt` timestamp ke connection data blob

**Frontend:**
- `ProviderDetailPage.jsx` — strategy dropdown (fill-first, round-robin) + stickyRoundRobinLimit input
- `CombosPage.jsx` — per-combo strategy dropdown (fallback, round-robin)

### Perbedaan Struktur

| Aspek | Original Node.js | FastAPI | Status |
|-------|-----------------|---------|--------|
| Connection selection | `auth.js:getProviderCredentials()` → 1 connection | `select_connection_for_provider()` → 1 connection | Sama |
| Fallback loop | `while(true)` dengan `excludeConnectionIds` | `while True` dengan `exclude_ids: set[str]` | Sama |
| Cooldown | `rateLimitedUntil` + exponential backoff | `calculate_cooldown()` + `mark_connection_unavailable()` | Sama |
| Model lock | `modelLock_<model>` field | `is_model_lock_active()` + `build_cooldown_update()` | Sama |
| Per-provider strategy | `providerStrategies[providerId]` | `get_provider_strategy()` reads from settings | Sama |
| Combo rotation | In-memory `Map` | In-memory `dict` | Sama |
| Connection cache | Tidak ada (DB query per request) | `get_connections_cached()` dengan 30s TTL | FastAPI lebih baik |
| Random jitter | Tidak ada | `random.randint()` pada round-robin index | FastAPI lebih baik |
| `lastUsedAt` tracking | Via `updateConnection()` | Via `update_connection_usage()` | Sama |
