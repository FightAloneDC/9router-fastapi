# Usage Menu Fix Plan

**Date:** 2026-05-30
**Status:** Draft
**Priority:** High

---

## Overview

Plan untuk memperbaiki issues pada Menu Usage berdasarkan hasil investigasi.

**Issues:**
1. Recent Requests data source mismatch
2. Canvas edges no live events
3. Token usage & cost tracking incomplete
4. Data synchronization between tables

---

## Phase 1: Fix Recent Requests Data Source

### Problem
Recent Requests queries from `usage_history` but Details queries from `request_details`. Data tidak sinkron.

### Solution
Query Recent Requests dari `request_details` table agar konsisten dengan Details tab.

### Changes

#### 1.1 Modify `backend/app/routers/usage.py`

**Current (lines 305-328):**
```python
# Recent requests (last 20)
recent_result = await db.execute(
    select(
        UsageHistory.timestamp,
        UsageHistory.model,
        UsageHistory.provider,
        UsageHistory.prompt_tokens,
        UsageHistory.completion_tokens,
        UsageHistory.status,
    )
    .where(UsageHistory.timestamp >= since)
    .order_by(UsageHistory.timestamp.desc())
    .limit(20)
)
```

**New:**
```python
# Recent requests (last 20) — from request_details for consistency
recent_result = await db.execute(
    select(
        RequestDetail.timestamp,
        RequestDetail.model,
        RequestDetail.provider,
        RequestDetail.prompt_tokens,
        RequestDetail.completion_tokens,
        RequestDetail.status,
    )
    .where(RequestDetail.timestamp >= since)
    .order_by(RequestDetail.timestamp.desc())
    .limit(20)
)
```

#### 1.2 Update import in `backend/app/routers/usage.py`

Add `RequestDetail` to imports (already imported at line 13).

### Verification
- Check Recent Requests shows same data as Details tab
- Verify timestamps match between both views

---

## Phase 2: Enable SSE + Active Request Tracking

### Problem
Canvas edges tidak animasi karena SSE disabled dan tidak ada active request tracking.

### Solution
1. Enable SSE di frontend
2. Tambahkan active request tracking di backend
3. Kirim active request events via SSE

### Changes

#### 2.1 Backend: Add Active Request Tracking

**New file: `backend/app/services/active_requests.py`**
```python
"""In-memory active request tracker for real-time canvas updates."""

import asyncio
import time
from dataclasses import dataclass, field

@dataclass
class ActiveRequest:
    provider: str
    model: str
    started_at: float = field(default_factory=time.time)

# In-memory store
_active_requests: dict[str, ActiveRequest] = {}

def track_request_start(provider: str, model: str) -> str:
    """Start tracking an active request. Returns request ID."""
    request_id = f"{provider}-{model}-{int(time.time() * 1000)}"
    _active_requests[request_id] = ActiveRequest(provider=provider, model=model)
    return request_id

def track_request_end(request_id: str):
    """Stop tracking a request."""
    _active_requests.pop(request_id, None)

def get_active_requests() -> list[dict]:
    """Get all active requests."""
    return [
        {"provider": r.provider, "model": r.model, "startedAt": r.started_at}
        for r in _active_requests.values()
    ]
```

#### 2.2 Backend: Modify Proxy Endpoints

**Modify `backend/app/routers/v1_proxy/chat.py`:**
```python
from app.services.active_requests import track_request_start, track_request_end

@router.post("/chat/completions")
async def chat_completions(...):
    # ... existing code ...
    
    while True:
        # ... existing code ...
        
        try:
            request_start_time: float = time.time()
            active_request_id = track_request_start(target.provider, target.model)
            
            if stream:
                resp = await _stream_response(...)
            else:
                resp, resp_data = await _non_stream_response(...)
            
            track_request_end(active_request_id)
            # ... rest of code ...
        except Exception as e:
            track_request_end(active_request_id)
            # ... rest of code ...
```

Apply same pattern to `messages.py`, `responses.py`, `embeddings.py`.

#### 2.3 Backend: Modify SSE Endpoint

**Modify `backend/app/routers/usage_stream.py`:**
```python
from app.services.active_requests import get_active_requests

async def _event_generator(queue: asyncio.Queue):
    """SSE generator that yields events from the queue."""
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25)
                active = get_active_requests()
                yield f"event: {event}\ndata: {json.dumps({'activeRequests': active})}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive with active requests
                active = get_active_requests()
                yield f"event: keepalive\ndata: {json.dumps({'activeRequests': active})}\n\n"
    except asyncio.CancelledError:
        pass
```

#### 2.4 Frontend: Enable SSE in UsagePage.jsx

**Uncomment and modify lines 1205-1225:**
```javascript
// SSE for real-time updates
useEffect(() => {
    if (activeTab !== 'overview') return
    const token = localStorage.getItem('token')
    if (!token) return
    
    let eventSource
    let reconnectTimer
    
    const connect = () => {
        eventSource = new EventSource(`/api/usage/stream?token=${token}`)
        
        eventSource.addEventListener('update', (e) => {
            const data = JSON.parse(e.data || '{}')
            if (data.activeRequests) {
                setActiveRequests(data.activeRequests)
            }
            fetchData(period)
        })
        
        eventSource.addEventListener('keepalive', (e) => {
            const data = JSON.parse(e.data || '{}')
            if (data.activeRequests) {
                setActiveRequests(data.activeRequests)
            }
        })
        
        eventSource.onerror = () => {
            eventSource.close()
            reconnectTimer = setTimeout(connect, 5000)
        }
    }
    
    connect()
    
    return () => {
        if (eventSource) eventSource.close()
        if (reconnectTimer) clearTimeout(reconnectTimer)
    }
}, [activeTab, period, fetchData])
```

#### 2.5 Frontend: Add State and Pass Props

**Add state in UsagePage:**
```javascript
const [activeRequests, setActiveRequests] = useState([])
const [lastProvider, setLastProvider] = useState('')
const [errorProvider, setErrorProvider] = useState('')
```

**Pass props to ProviderTopology (line 1283):**
```jsx
<ProviderTopology
    providers={stats?.byProvider || []}
    activeRequests={activeRequests}
    lastProvider={lastProvider}
    errorProvider={errorProvider}
/>
```

### Verification
- Make API request via `/v1/chat/completions`
- Check canvas edges animate during request
- Check edges stop animating after request completes

---

## Phase 3: Improve Cost Tracking

### Problem
Cost table incomplete, no custom rates, streaming usage edge cases.

### Solution
1. Expand cost table
2. Add custom cost rate configuration
3. Handle streaming usage edge cases

### Changes

#### 3.1 Expand Cost Table

**Modify `backend/app/services/usage_tracking.py`:**

Add more models to `_COST_TABLE`:
```python
_COST_TABLE: list[tuple[str, float, float]] = [
    # ... existing entries ...
    
    # Additional models
    ("gpt-4.1", 2.0, 8.0),
    ("gpt-4.1-mini", 0.4, 1.6),
    ("gpt-4.1-nano", 0.1, 0.4),
    ("o3-mini", 1.1, 4.4),
    ("claude-3.5-sonnet", 3.0, 15.0),
    ("claude-3.5-haiku", 0.8, 4.0),
    ("gemini-2.0-pro", 1.25, 10.0),
    ("gemini-2.5-flash-preview", 0.15, 0.6),
    ("deepseek-coder", 0.14, 0.28),
    ("qwen2.5", 0.05, 0.2),
    ("llama-3.2", 0.05, 0.08),
    ("command-r-plus", 2.5, 10.0),
    ("command-r", 0.15, 0.6),
]
```

#### 3.2 Add Custom Cost Rate Configuration

**Add to Settings model:**
```python
# In SettingsModel.data JSON:
{
    "customCostRates": {
        "provider/model": {
            "input": 2.5,  # $/M tokens
            "output": 10.0
        }
    }
}
```

**Modify `_calculate_cost()`:**
```python
async def _calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    provider: str = None,
    db: AsyncSession = None,
) -> float:
    """Calculate cost based on model name and token counts."""
    if not model:
        return 0.0
    
    # Check custom rates first
    if db and provider:
        result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
        row = result.scalar_one_or_none()
        if row and row.data:
            data = json.loads(row.data)
            custom_rates = data.get("customCostRates", {})
            rate_key = f"{provider}/{model}"
            if rate_key in custom_rates:
                rate = custom_rates[rate_key]
                return (prompt_tokens * rate["input"] + completion_tokens * rate["output"]) / 1_000_000
    
    # Fallback to built-in table
    model_lower = model.lower()
    for prefix, input_rate, output_rate in _COST_TABLE:
        if prefix in model_lower:
            return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
    
    # Default rate
    return (prompt_tokens * 1.0 + completion_tokens * 2.0) / 1_000_000
```

#### 3.3 Handle Streaming Usage Edge Cases

**Modify `backend/app/routers/v1_proxy/shared.py`:**

Add fallback for missing usage in streaming:
```python
async def generate():
    usage: dict = {}
    chunk_count = 0
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            async with client.stream("POST", target.url, **send_kwargs) as resp:
                async for chunk in resp.aiter_bytes():
                    chunk_count += 1
                    # ... existing code ...
        except Exception as e:
            # ... existing code ...
        finally:
            yield b"data: [DONE]\n\n"
    
    # If no usage captured, estimate from response
    if not usage.get("prompt_tokens") and not usage.get("completion_tokens"):
        # Estimate based on chunk count (rough approximation)
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": chunk_count * 10,  # rough estimate
            "total_tokens": chunk_count * 10,
        }
    
    # ... rest of tracking code ...
```

### Verification
- Test with models not in cost table → should use default rate
- Test with custom rate configured → should use custom rate
- Test streaming with provider that doesn't send usage → should estimate

---

## Phase 4: Data Consistency

### Problem
`save_request_usage` and `save_request_detail` called separately, may fail independently.

### Solution
Wrap both saves in single transaction.

### Changes

#### 4.1 Create Combined Save Function

**Modify `backend/app/services/usage_tracking.py`:**

```python
async def save_request_tracking(
    db: AsyncSession,
    *,
    provider: str | None = None,
    model: str | None = None,
    connection_id: str | None = None,
    api_key: str | None = None,
    endpoint: str | None = None,
    status: str = "ok",
    latency_ttft: int | None = None,
    latency_total: int | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    tokens_json: dict | None = None,
    meta_json: dict | None = None,
    request_body: dict | None = None,
    provider_request_body: dict | None = None,
    provider_response_body: dict | None = None,
    response_body: dict | None = None,
) -> None:
    """Save both usage history and request detail in single transaction."""
    try:
        cost = _calculate_cost(model or "", prompt_tokens, completion_tokens)
        now = datetime.now(timezone.utc)
        
        # 1. Insert into usage_history
        usage_row = UsageHistory(
            timestamp=now,
            provider=provider,
            model=model,
            connection_id=connection_id,
            api_key=api_key,
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            status=status,
            tokens=json.dumps(tokens_json or {}),
            meta=json.dumps(meta_json or {}),
        )
        db.add(usage_row)
        
        # 2. Insert into request_details
        detail_row = RequestDetail(
            provider=provider,
            model=model,
            connection_id=connection_id,
            status=status,
            latency_ttft=latency_ttft,
            latency_total=latency_total,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            request=json.dumps(_sanitize_payload(request_body, sanitize_headers=True)),
            provider_request=json.dumps(_sanitize_payload(provider_request_body)),
            provider_response=json.dumps(_sanitize_payload(provider_response_body)),
            response=json.dumps(_sanitize_payload(response_body)),
        )
        db.add(detail_row)
        
        # 3. Upsert usage_daily
        date_key = _get_date_key()
        result = await db.execute(
            select(UsageDaily).where(UsageDaily.date_key == date_key)
        )
        daily = result.scalar_one_or_none()
        
        if daily:
            day_data = json.loads(daily.data) if daily.data else {}
        else:
            day_data = {
                "requests": 0,
                "promptTokens": 0,
                "completionTokens": 0,
                "cost": 0,
                "byProvider": {},
                "byModel": {},
            }
        
        day_data["requests"] = day_data.get("requests", 0) + 1
        day_data["promptTokens"] = day_data.get("promptTokens", 0) + prompt_tokens
        day_data["completionTokens"] = day_data.get("completionTokens", 0) + completion_tokens
        day_data["cost"] = day_data.get("cost", 0) + cost
        
        if provider:
            bp = day_data.setdefault("byProvider", {})
            p = bp.setdefault(provider, {"requests": 0, "promptTokens": 0, "completionTokens": 0, "cost": 0})
            p["requests"] += 1
            p["promptTokens"] += prompt_tokens
            p["completionTokens"] += completion_tokens
            p["cost"] += cost
        
        if model:
            bm = day_data.setdefault("byModel", {})
            model_key = f"{model}|{provider}" if provider else model
            m = bm.setdefault(model_key, {"requests": 0, "promptTokens": 0, "completionTokens": 0, "cost": 0, "rawModel": model, "provider": provider or ""})
            m["requests"] += 1
            m["promptTokens"] += prompt_tokens
            m["completionTokens"] += completion_tokens
            m["cost"] += cost
        
        if daily:
            daily.data = json.dumps(day_data)
        else:
            db.add(UsageDaily(date_key=date_key, data=json.dumps(day_data)))
        
        # Commit all at once
        await db.commit()
        
        # Cleanup old details (non-blocking)
        await cleanup_old_details(db)
        
    except Exception as e:
        logger.error(f"Failed to save request tracking: {e}")
        await db.rollback()
```

#### 4.2 Update Proxy Endpoints

**Modify all proxy endpoints to use combined function:**

```python
# Instead of:
await save_request_usage(db, ...)
await save_request_detail(db, ...)

# Use:
await save_request_tracking(
    db,
    provider=target.provider,
    model=target.model,
    connection_id=target.connection_id,
    endpoint="/v1/chat/completions",
    prompt_tokens=prompt_tokens,
    completion_tokens=completion_tokens,
    tokens_json=usage,
    request_body=body,
    provider_request_body=forward_body,
    provider_response_body=resp_data,
    response_body=resp_data,
)
```

### Verification
- Check both tables have same record count
- Simulate failure in one save → should rollback both
- Check data consistency between tables

---

## Implementation Order

1. **Phase 1** (Quick fix) — 1-2 hours
   - Fix Recent Requests data source
   - Immediate improvement for user experience

2. **Phase 2** (Medium effort) — 4-6 hours
   - Enable SSE
   - Add active request tracking
   - Connect canvas edges

3. **Phase 3** (Enhancement) — 2-3 hours
   - Expand cost table
   - Add custom rates
   - Handle edge cases

4. **Phase 4** (Robustness) — 2-3 hours
   - Combined save function
   - Transaction wrapping
   - Data consistency

**Total estimated effort:** 9-14 hours

---

## Testing Plan

### Unit Tests
- Test `_calculate_cost()` with various models
- Test `save_request_tracking()` transaction rollback
- Test `track_request_start/end` lifecycle

### Integration Tests
- Make API request → verify both tables updated
- Check SSE events during request
- Verify canvas edge animation

### Manual Testing
1. Send request via `/v1/chat/completions`
2. Check Usage Overview → Recent Requests shows request
3. Check Usage Details → same request appears
4. Check canvas edges animate during request
5. Check cost calculation is reasonable

---

## Rollback Plan

If issues arise:
1. Phase 1: Revert `usage.py` changes
2. Phase 2: Comment out SSE code again
3. Phase 3: Revert `_COST_TABLE` changes
4. Phase 4: Revert to separate save functions

---

## Success Criteria

- [ ] Recent Requests shows same data as Details tab
- [ ] Canvas edges animate during active requests
- [ ] Cost calculation covers 90%+ of common models
- [ ] Data consistency between `usage_history` and `request_details`
- [ ] No data loss during tracking failures
