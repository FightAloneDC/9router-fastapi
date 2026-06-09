# Plan: POST /v1/messages

**Status:** Not started  
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Original source:** `~/dev/9router/src/app/api/v1/messages/route.js` → `src/sse/handlers/chat.js`  
**Estimated effort:** Low-Medium — route alias + format translation layer (Claude ↔ OpenAI).

---

## What This Does

Adds an Anthropic Claude-compatible messages endpoint to the FastAPI proxy.
Clients send requests in Claude's `/v1/messages` format, 9Router translates
to the upstream provider's format (OpenAI or Claude), forwards the request,
and returns the response in Claude format.

```
Client → POST /v1/messages { model: "an/claude-sonnet-4", system: "You are helpful", messages: [...], max_tokens: 1024 }
           ↓
       detect format: Claude (from /v1/messages path)
           ↓
       resolve model → provider "anthropic"
           ↓
       if upstream is Claude-format → forward as-is to {base}/messages
       if upstream is OpenAI-format → translate Claude→OpenAI, forward to {base}/chat/completions
           ↓
       if upstream returned Claude format → return as-is
       if upstream returned OpenAI format → translate OpenAI→Claude, return
```

---

## Background: How the Original Works

In the original Next.js 9router, `/v1/messages` is a thin wrapper:

```javascript
// src/app/api/v1/messages/route.js
export async function POST(request) {
  await ensureInitialized();  // init translators
  return await handleChat(request);  // same handler as /v1/chat/completions
}
```

The magic is in the **translator layer** (`open-sse/translator/`):

1. `detectFormatByEndpoint(pathname, body)` — detects format from URL:
   - `/v1/messages` → `FORMATS.CLAUDE`
   - `/v1/chat/completions` → `FORMATS.OPENAI`
   - `/v1/responses` → `FORMATS.OPENAI_RESPONSES`

2. `translate(from, to, model, body, stream)` — converts between formats:
   - `claude → openai`: extracts `system` to system message, converts
     `content` blocks, maps `max_tokens` → `max_completion_tokens`, etc.
   - `openai → claude`: extracts system messages to `system` field, converts
     message format, maps tool calls, etc.

3. The response is also translated back to the client's expected format.

---

## Current State in FastAPI Port

The existing `POST /v1/chat/completions` handler:

1. ✅ Resolves model → provider → upstream target (via `resolve_model_to_targets`)
2. ✅ Builds correct upstream URL — `{base}/messages` for Claude providers,
   `{base}/chat/completions` for OpenAI providers
3. ✅ Builds correct headers — `x-api-key` + `anthropic-version` for Claude,
   `Authorization: Bearer` for OpenAI
4. ✅ Forwards body as-is to upstream
5. ✅ Returns upstream response as-is to client

**What's missing:**
- ❌ No `/v1/messages` route
- ❌ No format detection (doesn't know if client sent Claude or OpenAI format)
- ❌ No request translation (Claude format → OpenAI format when targeting OpenAI provider)
- ❌ No response translation (OpenAI format → Claude format when client expects Claude)

---

## Key Format Differences

### Request: Claude Format
```json
{
  "model": "claude-sonnet-4",
  "max_tokens": 1024,
  "system": "You are a helpful assistant.",
  "messages": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi! How can I help?" },
    { "role": "user", "content": "What's the weather?" }
  ],
  "tools": [
    {
      "name": "get_weather",
      "description": "Get weather for a location",
      "input_schema": { "type": "object", "properties": { "location": { "type": "string" } } }
    }
  ],
  "stream": true
}
```

### Request: OpenAI Format
```json
{
  "model": "gpt-4o",
  "max_tokens": 1024,
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi! How can I help?" },
    { "role": "user", "content": "What's the weather?" }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": { "type": "object", "properties": { "location": { "type": "string" } } }
      }
    }
  ],
  "stream": true
}
```

### Key Differences:
| Field | Claude | OpenAI |
|-------|--------|--------|
| System prompt | `system` (top-level string/array) | `messages[0].role == "system"` |
| Max tokens | `max_tokens` | `max_tokens` or `max_completion_tokens` |
| Tools | `tools[].input_schema` | `tools[].function.parameters` |
| Tool use | `content[].type == "tool_use"` | `tool_calls[].function` |
| Tool result | `content[].type == "tool_result"` | `role: "tool"` message |
| Stop reason | `stop_reason: "end_turn"` | `finish_reason: "stop"` |
| Usage | `usage.input_tokens` + `usage.output_tokens` | `usage.prompt_tokens` + `usage.completion_tokens` |

### Response: Claude Format
```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "content": [{ "type": "text", "text": "The weather is sunny." }],
  "model": "claude-sonnet-4",
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 50, "output_tokens": 20 }
}
```

### Response: OpenAI Format
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "choices": [{
    "index": 0,
    "message": { "role": "assistant", "content": "The weather is sunny." },
    "finish_reason": "stop"
  }],
  "model": "gpt-4o",
  "usage": { "prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70 }
}
```

---

## Phase 1 — Backend: Format Translation Layer

**New file:** `backend/app/services/format_translator.py`

### 1.1 Claude → OpenAI Request Translator

```python
def claude_to_openai_request(body: dict) -> dict:
    """Convert Claude messages format to OpenAI chat completions format."""
    result = {
        "model": body.get("model", ""),
        "stream": body.get("stream", False),
    }
    
    # Max tokens
    if "max_tokens" in body:
        result["max_tokens"] = body["max_tokens"]
    
    # Temperature
    if "temperature" in body:
        result["temperature"] = body["temperature"]
    
    # Messages: extract system → system message
    messages = []
    
    # System prompt (top-level in Claude format)
    system = body.get("system")
    if system:
        if isinstance(system, list):
            system_text = "\n".join(s.get("text", "") for s in system if isinstance(s, dict))
        else:
            system_text = str(system)
        if system_text:
            messages.append({"role": "system", "content": system_text})
    
    # Convert messages
    for msg in body.get("messages", []):
        converted = _convert_claude_message(msg)
        if converted:
            if isinstance(converted, list):
                messages.extend(converted)
            else:
                messages.append(converted)
    
    result["messages"] = messages
    
    # Tools: Claude input_schema → OpenAI function parameters
    if "tools" in body:
        result["tools"] = []
        for tool in body["tools"]:
            result["tools"].append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            })
    
    # Stop sequences
    if "stop_sequences" in body:
        result["stop"] = body["stop_sequences"]
    
    return result


def _convert_claude_message(msg: dict) -> dict | list | None:
    """Convert a single Claude message to OpenAI format."""
    role = msg.get("role", "user")
    content = msg.get("content")
    
    # Simple string content
    if isinstance(content, str):
        return {"role": role, "content": content}
    
    # Array content (may contain text, tool_use, tool_result blocks)
    if isinstance(content, list):
        text_parts = []
        tool_calls = []
        tool_results = []
        
        for block in content:
            block_type = block.get("type", "")
            
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            
            elif block_type == "tool_use":
                # Claude tool_use → OpenAI tool_calls
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {})),
                    }
                })
            
            elif block_type == "tool_result":
                # Claude tool_result → OpenAI tool message
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    result_content = "\n".join(
                        b.get("text", "") for b in result_content if b.get("type") == "text"
                    )
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id", ""),
                    "content": str(result_content),
                })
        
        # Build OpenAI message
        if tool_calls and role == "assistant":
            return {
                "role": "assistant",
                "content": "\n".join(text_parts) if text_parts else None,
                "tool_calls": tool_calls,
            }
        
        if tool_results:
            results = []
            if text_parts:
                results.append({"role": role, "content": "\n".join(text_parts)})
            results.extend(tool_results)
            return results
        
        return {"role": role, "content": "\n".join(text_parts)}
    
    return {"role": role, "content": str(content) if content else ""}
```

### 1.2 OpenAI → Claude Response Translator

```python
def openai_to_claude_response(data: dict, model: str = "") -> dict:
    """Convert OpenAI chat completion response to Claude messages format."""
    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "stop")
    
    # Map finish_reason → stop_reason
    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }
    stop_reason = stop_reason_map.get(finish_reason, "end_turn")
    
    # Build content blocks
    content = []
    
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})
    
    # Tool calls → tool_use blocks
    for tc in message.get("tool_calls", []):
        func = tc.get("function", {})
        try:
            input_args = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            input_args = {}
        content.append({
            "type": "tool_use",
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            "input": input_args,
        })
    
    if not content:
        content.append({"type": "text", "text": ""})
    
    # Usage
    usage = data.get("usage", {})
    
    return {
        "id": data.get("id", "").replace("chatcmpl-", "msg_"),
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": model or data.get("model", ""),
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }
```

### 1.3 OpenAI → Claude Streaming Response Translator

```python
def openai_to_claude_stream_chunk(chunk_data: dict, model: str = "") -> dict | None:
    """Convert OpenAI SSE chunk to Claude streaming event format."""
    choice = chunk_data.get("choices", [{}])[0]
    delta = choice.get("delta", {})
    
    events = []
    
    # Text content delta
    if delta.get("content"):
        events.append({
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": delta["content"]},
        })
    
    # Tool call deltas
    for tc in delta.get("tool_calls", []):
        func = tc.get("function", {})
        if func.get("name"):
            # New tool call start
            events.append({
                "type": "content_block_start",
                "index": tc.get("index", 0) + 1,
                "content_block": {
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": func["name"],
                    "input": {},
                },
            })
        if func.get("arguments"):
            # Tool call arguments delta
            events.append({
                "type": "content_block_delta",
                "index": tc.get("index", 0) + 1,
                "delta": {"type": "input_json_delta", "partial_json": func["arguments"]},
            })
    
    # Finish reason
    finish_reason = choice.get("finish_reason")
    if finish_reason:
        stop_reason_map = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use"}
        events.append({
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason_map.get(finish_reason, "end_turn")},
            "usage": {"output_tokens": chunk_data.get("usage", {}).get("completion_tokens", 0)},
        })
    
    return events
```

### 1.4 Claude → OpenAI Streaming Response Translator

For when client sends Claude format but upstream is OpenAI — translate response
chunks back to Claude SSE format.

This is more complex because Claude SSE uses different event types:
- `message_start` — initial message metadata
- `content_block_start` — start of a content block
- `content_block_delta` — incremental content
- `content_block_stop` — end of content block
- `message_delta` — final metadata (stop_reason, usage)
- `message_stop` — end of message

---

## Phase 2 — Backend: Format Detection Helper

```python
def detect_request_format(path: str, body: dict) -> str:
    """Detect request format from URL path and body shape."""
    if "/v1/messages" in path:
        return "claude"
    if "/v1/responses" in path:
        return "openai-responses"
    # Default: OpenAI
    return "openai"

def detect_response_format(data: dict) -> str:
    """Detect response format from response shape."""
    if "type" in data and data.get("type") == "message":
        return "claude"
    if "choices" in data:
        return "openai"
    return "openai"
```

---

## Phase 3 — Backend: Add `/v1/messages` Route

**File:** `backend/app/routers/v1_proxy.py`

The route handler follows the same pattern as `chat_completions` but with
format translation:

```python
@router.post("/messages")
async def messages(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """Anthropic Claude-compatible messages proxy.
    
    Accepts Claude messages format and routes to the appropriate provider.
    Translates between Claude and OpenAI formats as needed.
    """
    from app.services.format_translator import (
        claude_to_openai_request,
        openai_to_claude_response,
        detect_response_format,
    )
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="Missing required field: model")
    
    stream = body.get("stream", False)
    request_id = str(uuid.uuid4())
    
    # Client sent Claude format — detect upstream provider format
    targets = await resolve_model_to_targets(db, model, stream)
    if not targets:
        raise HTTPException(status_code=503, detail=f"No provider available for model: {model}")
    
    strategy, sticky_limit = await get_combo_strategy(db)
    targets = _get_rotated_targets(targets, model, strategy, sticky_limit)
    
    last_error = None
    for target in targets:
        # Check upstream provider format
        cfg = PROVIDER_CONFIGS.get(target.provider, {})
        upstream_format = cfg.get("format", "openai")
        
        # Translate request body if needed
        if upstream_format == "claude":
            # Upstream is Claude — forward as-is
            forward_body = {**body, "model": target.model}
        else:
            # Upstream is OpenAI — translate Claude → OpenAI
            forward_body = claude_to_openai_request({**body, "model": target.model})
        
        try:
            if stream:
                return await _stream_messages_response(target, forward_body, request_id, upstream_format)
            else:
                return await _non_stream_messages_response(target, forward_body, request_id, upstream_format)
        except httpx.HTTPStatusError as e:
            last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
            if e.response.status_code < 500:
                return JSONResponse(status_code=e.response.status_code, content={"error": {"message": e.response.text[:500]}})
            continue
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)}
            continue
    
    error_msg = last_error.get("detail", "All providers failed") if last_error else "No targets"
    error_status = last_error.get("status", 503) if last_error else 503
    return JSONResponse(status_code=error_status, content={"error": {"message": error_msg}})


async def _non_stream_messages_response(target, body, request_id, upstream_format):
    """Forward to upstream and translate response to Claude format if needed."""
    from app.services.format_translator import openai_to_claude_response
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(target.url, json=body, headers=target.headers)
        resp.raise_for_status()
        data = resp.json()
    
    # If upstream is OpenAI, translate to Claude format
    if upstream_format != "claude":
        data = openai_to_claude_response(data, target.model)
    
    return JSONResponse(status_code=200, content=data, headers={"X-Request-Id": request_id})
```

---

## Phase 4 — Frontend: No Changes Required

The `/v1/messages` endpoint is a pure API endpoint. No UI changes needed.

---

## Phase 5 — Testing

### 5.1 Manual curl tests

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — Claude format → Anthropic provider (passthrough):**
```bash
curl -s -X POST http://localhost:9000/v1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "an/claude-sonnet-4",
    "max_tokens": 100,
    "system": "You are a helpful assistant.",
    "messages": [{"role": "user", "content": "Say hello in one word."}]
  }' | jq '{id, type, role, stop_reason, content: .content[0].text}'
```
Expected: Claude format response with `type: "message"`, `stop_reason: "end_turn"`.

**Test 2 — Claude format → OpenAI provider (translation):**
```bash
curl -s -X POST http://localhost:9000/v1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "max_tokens": 100,
    "system": "You are a helpful assistant.",
    "messages": [{"role": "user", "content": "Say hello in one word."}]
  }' | jq '{id, type, role, stop_reason, content: .content[0].text}'
```
Expected: Claude format response (translated from OpenAI upstream).

**Test 3 — Claude format with tools:**
```bash
curl -s -X POST http://localhost:9000/v1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "max_tokens": 200,
    "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}],
    "tools": [{
      "name": "get_weather",
      "description": "Get weather for a location",
      "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}}
    }]
  }' | jq '{stop_reason, content_types: [.content[].type]}'
```
Expected: `stop_reason: "tool_use"`, content contains `tool_use` block.

**Test 4 — Missing model (400):**
```bash
curl -s -X POST http://localhost:9000/v1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}' | jq .
```
Expected: `400` with `"Missing required field: model"`.

**Test 5 — Streaming:**
```bash
curl -s -X POST http://localhost:9000/v1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "an/claude-sonnet-4",
    "max_tokens": 100,
    "stream": true,
    "messages": [{"role": "user", "content": "Say hello."}]
  }' | head -20
```
Expected: Claude SSE events (`message_start`, `content_block_delta`, etc.).

### 5.2 Regression check

```bash
# Existing chat completions still works
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```

---

## Phase 6 — Report

1. **`docs/porting-status.md`** — Move `POST /v1/messages` to "Fully Ported".
2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 8 as ✅.
3. **`docs/plans/v1-messages.md`** (this file) — Update status to `Done`.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Streaming translation | Claude SSE format is different from OpenAI SSE. Streaming translation adds significant complexity. Phase 1 focuses on non-streaming. |
| Tool use translation | Claude `tool_use` blocks ↔ OpenAI `tool_calls` array. Basic translation works but edge cases (parallel tool calls, partial JSON) may need refinement. |
| `content` array with mixed types | Claude messages can have mixed `text` + `tool_use` + `tool_result` blocks in one message. The translator handles common cases but complex nested structures may not translate perfectly. |
| Token counting | Claude counts tokens differently from OpenAI. The translated `usage` fields are approximate. |
| Extended thinking | Claude's extended thinking (`thinking` blocks) is not translated in Phase 1. |
| Multi-turn tool conversations | Complex multi-turn tool use conversations may lose context during translation. |
| `top_k`, `top_p` | Claude-specific sampling params not mapped to OpenAI equivalents. |
| `metadata` | Claude's `metadata.user_id` not mapped. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/format_translator.py` | NEW — Claude ↔ OpenAI format translation |
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/messages` handler |
| `docs/porting-status.md` | Move messages endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 8 done |
| `docs/plans/v1-messages.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Route handler | Low | Same pattern as chat_completions |
| Claude → OpenAI request translation | Medium | System extraction, message conversion, tool mapping |
| OpenAI → Claude response translation | Medium | Content block building, stop_reason mapping |
| Streaming translation | High | Different SSE event formats (Phase 2 follow-up) |
| Tool use translation | Medium | Claude tool_use ↔ OpenAI tool_calls |
| Format detection | Trivial | URL path check |

**Overall:** Low-Medium complexity. The route handler is trivial (alias pattern).
The complexity is in the format translation layer. Non-streaming translation is
straightforward. Streaming translation is significantly harder and can be a
Phase 2 follow-up.

**Recommended implementation order:**
1. Route alias (no translation — just forward to Claude providers)
2. Claude → OpenAI request translation (for targeting OpenAI providers)
3. OpenAI → Claude response translation (non-streaming)
4. Streaming translation (Phase 2 follow-up)
