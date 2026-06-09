# Plan: POST /v1/responses

**Status:** Not started  
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Original source:** `~/dev/9router/src/app/api/v1/responses/route.js` → `src/sse/handlers/chat.js` → translator layer  
**Estimated effort:** High — format translation is significantly more complex than `/v1/messages` due to fundamentally different SSE event format.

---

## What This Does

Adds an OpenAI Responses API endpoint to the FastAPI proxy. Clients send
requests in Responses API format (`input[]`, `instructions`), 9Router
translates to Chat Completions format (`messages[]`, system message),
forwards to the upstream provider, and translates the response back to
Responses API format.

```
Client → POST /v1/responses { model: "openai/gpt-4o", instructions: "You are helpful", input: [...] }
           ↓
       detect format: Responses API (from /v1/responses path)
           ↓
       translate request: Responses API → Chat Completions
           ↓
       resolve model → provider → upstream target
           ↓
       POST upstream /chat/completions { model, messages, tools, ... }
           ↓
       translate response: Chat Completions → Responses API
           ↓
       return Responses API format (SSE events or JSON)
```

---

## Background: What is the OpenAI Responses API?

The Responses API is OpenAI's newer API format (2025+), designed as a
replacement for Chat Completions. Key differences:

### Request Format

**Chat Completions (old):**
```json
{
  "model": "gpt-4o",
  "messages": [
    { "role": "system", "content": "You are helpful." },
    { "role": "user", "content": "Hello" }
  ],
  "tools": [{ "type": "function", "function": { "name": "search", "parameters": {...} } }]
}
```

**Responses API (new):**
```json
{
  "model": "gpt-4o",
  "instructions": "You are helpful.",
  "input": [
    { "type": "message", "role": "user", "content": [{ "type": "input_text", "text": "Hello" }] }
  ],
  "tools": [{ "type": "function", "name": "search", "parameters": {...} }]
}
```

### Response Format (Streaming)

**Chat Completions SSE:**
```
data: {"id":"chatcmpl-1","choices":[{"delta":{"content":"Hello"}}]}
data: {"id":"chatcmpl-1","choices":[{"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

**Responses API SSE:**
```
event: response.created
data: {"type":"response.created","response":{"id":"resp_1","status":"in_progress","output":[]}}

event: response.in_progress
data: {"type":"response.in_progress","response":{"id":"resp_1","status":"in_progress"}}

event: response.output_item.added
data: {"type":"response.output_item.added","output_index":0,"item":{"type":"message","role":"assistant","content":[]}}

event: response.content_part.added
data: {"type":"response.content_part.added","output_index":0,"content_index":0,"part":{"type":"output_text","text":""}}

event: response.output_text.delta
data: {"type":"response.output_text.delta","output_index":0,"content_index":0,"delta":"Hello"}

event: response.output_text.done
data: {"type":"response.output_text.done","output_index":0,"content_index":0,"text":"Hello"}

event: response.content_part.done
data: {"type":"response.content_part.done","output_index":0,"content_index":0,"part":{"type":"output_text","text":"Hello"}}

event: response.output_item.done
data: {"type":"response.output_item.done","output_index":0,"item":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Hello"}]}}

event: response.completed
data: {"type":"response.completed","response":{"id":"resp_1","status":"completed","output":[...],"usage":{...}}}
```

---

## Key Format Differences

### Request

| Field | Responses API | Chat Completions |
|-------|--------------|------------------|
| System prompt | `instructions` (top-level string) | `messages[0].role == "system"` |
| Messages | `input[]` array with typed items | `messages[]` array with role/content |
| User message | `{ type: "message", role: "user", content: [{ type: "input_text", text }] }` | `{ role: "user", content: "text" }` |
| Assistant message | `{ type: "message", role: "assistant", content: [{ type: "output_text", text }] }` | `{ role: "assistant", content: "text" }` |
| Tool call | `{ type: "function_call", call_id, name, arguments }` | `{ role: "assistant", tool_calls: [{ id, function: { name, arguments } }] }` |
| Tool result | `{ type: "function_call_output", call_id, output }` | `{ role: "tool", tool_call_id, content }` |
| Reasoning | `{ type: "reasoning", summary: [{ text }] }` | `delta.reasoning_content` in streaming |
| Tools | `{ type: "function", name, parameters }` | `{ type: "function", function: { name, parameters } }` |
| Images | `{ type: "input_image", image_url: "url" }` | `{ type: "image_url", image_url: { url } }` |

### Response (Streaming)

| Event | Responses API | Chat Completions |
|-------|--------------|------------------|
| Start | `response.created` + `response.in_progress` | First `data: {"choices":[...]}` chunk |
| Text delta | `response.output_text.delta` | `delta.content` |
| Tool call start | `response.function_call_arguments.done` | `delta.tool_calls[0]` with `function.name` |
| Tool call delta | N/A (sent as complete) | `delta.tool_calls[0].function.arguments` |
| Finish | `response.completed` | `finish_reason: "stop"` + `data: [DONE]` |
| Sequence | Each event has `sequence_number` | No sequence numbers |

---

## Phase 1 — Backend: Request Translator (Responses API → Chat Completions)

**New file:** `backend/app/services/responses_translator.py`

### 1.1 Normalize Input

```python
def normalize_responses_input(input_data) -> list[dict] | None:
    """Normalize Responses API input to array format.
    
    Accepts string or array. Returns array of message items.
    Empty input injects placeholder (providers require at least one user message).
    """
    if isinstance(input_data, str):
        text = input_data.strip() or "..."
        return [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}]
    
    if isinstance(input_data, list):
        if len(input_data) == 0:
            return [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "..."}]}]
        return input_data
    
    return None
```

### 1.2 Main Request Translator

```python
def responses_to_chat_completions(body: dict) -> dict:
    """Convert OpenAI Responses API request to Chat Completions format.
    
    Key transformations:
    - instructions → system message
    - input[] → messages[]
    - input_text/output_text → text content
    - input_image → image_url content
    - function_call → tool_calls
    - function_call_output → tool message
    - reasoning → buffered and attached to next assistant message
    - tools format: { name, parameters } → { function: { name, parameters } }
    """
    if "input" not in body:
        return body  # Already in Chat Completions format
    
    result = {**body}
    result["messages"] = []
    
    # instructions → system message
    if body.get("instructions"):
        result["messages"].append({"role": "system", "content": body["instructions"]})
    
    # Parse input items
    input_items = normalize_responses_input(body["input"])
    if input_items is None:
        return body
    
    current_assistant_msg = None
    pending_reasoning = ""
    
    for item in input_items:
        item_type = item.get("type") or ("message" if "role" in item else None)
        
        if item_type == "message":
            # Flush pending assistant message
            if current_assistant_msg:
                result["messages"].append(current_assistant_msg)
                current_assistant_msg = None
            
            # Convert content blocks
            content = _convert_content_blocks(item.get("content", []), item.get("role", "user"))
            
            msg = {"role": item.get("role", "user"), "content": content}
            
            # Attach buffered reasoning to assistant messages
            if item.get("role") == "assistant" and pending_reasoning:
                msg["reasoning_content"] = pending_reasoning
                pending_reasoning = ""
            
            result["messages"].append(msg)
        
        elif item_type == "function_call":
            # Build assistant message with tool_calls
            if not current_assistant_msg:
                current_assistant_msg = {"role": "assistant", "content": None, "tool_calls": []}
                if pending_reasoning:
                    current_assistant_msg["reasoning_content"] = pending_reasoning
                    pending_reasoning = ""
            
            name = item.get("name", "")
            if name and name.strip():
                current_assistant_msg["tool_calls"].append({
                    "id": item.get("call_id", ""),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": item.get("arguments", "{}"),
                    },
                })
        
        elif item_type == "function_call_output":
            # Flush assistant message first
            if current_assistant_msg:
                result["messages"].append(current_assistant_msg)
                current_assistant_msg = None
            
            output = item.get("output", "")
            if not isinstance(output, str):
                output = json.dumps(output)
            
            result["messages"].append({
                "role": "tool",
                "tool_call_id": item.get("call_id", ""),
                "content": output,
            })
        
        elif item_type == "reasoning":
            # Buffer reasoning text for next assistant message
            text = _extract_reasoning_text(item)
            if text:
                pending_reasoning = f"{pending_reasoning}\n{text}" if pending_reasoning else text
    
    # Flush remaining
    if current_assistant_msg:
        result["messages"].append(current_assistant_msg)
    
    # Convert tools format
    if "tools" in body and isinstance(body["tools"], list):
        result["tools"] = []
        for tool in body["tools"]:
            if "function" in tool:
                result["tools"].append(tool)  # Already Chat Completions format
            elif tool.get("name"):
                result["tools"].append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": _normalize_tool_params(tool.get("parameters")),
                    },
                })
    
    # Cleanup Responses API specific fields
    for field in ["input", "instructions", "include", "store", "reasoning", "prompt_cache_key"]:
        result.pop(field, None)
    
    return result


def _convert_content_blocks(content, role: str) -> str | list:
    """Convert Responses API content blocks to Chat Completions format."""
    if isinstance(content, str):
        return content
    
    if not isinstance(content, list):
        return str(content) if content else ""
    
    text_parts = []
    for block in content:
        block_type = block.get("type", "")
        
        if block_type in ("input_text", "output_text"):
            text_parts.append(block.get("text", ""))
        elif block_type == "input_image":
            # Convert to image_url format
            url = block.get("image_url") or block.get("file_id", "")
            return [{"type": "image_url", "image_url": {"url": url, "detail": block.get("detail", "auto")}}]
        else:
            # Unknown type — serialize as text
            text = block.get("text") or block.get("content") or json.dumps(block)
            text_parts.append(str(text))
    
    return "\n".join(text_parts) if text_parts else ""


def _extract_reasoning_text(item: dict) -> str:
    """Extract reasoning text from a reasoning item."""
    if isinstance(item.get("summary"), list):
        text = "\n".join(s.get("text", "") for s in item["summary"] if isinstance(s, dict))
        if text:
            return text
    
    if isinstance(item.get("content"), list):
        text = "\n".join(c.get("text", "") for c in item["content"] if isinstance(c, dict))
        if text:
            return text
    
    return ""


def _normalize_tool_params(params: dict) -> dict:
    """Ensure tool parameters always have properties field."""
    if not params:
        return {"type": "object", "properties": {}}
    if params.get("type") == "object" and "properties" not in params:
        return {**params, "properties": {}}
    return params
```

---

## Phase 2 — Backend: Response Translator (Chat Completions → Responses API)

### 2.1 Non-Streaming Response Translator

```python
def chat_completions_to_responses(data: dict, model: str = "") -> dict:
    """Convert OpenAI Chat Completions response to Responses API format."""
    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "stop")
    
    # Map finish_reason → status
    status_map = {
        "stop": "completed",
        "length": "incomplete",
        "tool_calls": "completed",
    }
    status = status_map.get(finish_reason, "completed")
    
    # Build output items
    output = []
    
    # Message output
    content_blocks = []
    if message.get("content"):
        content_blocks.append({
            "type": "output_text",
            "annotations": [],
            "text": message["content"],
        })
    
    # Tool calls → function_call outputs
    for tc in message.get("tool_calls", []):
        func = tc.get("function", {})
        output.append({
            "type": "function_call",
            "id": tc.get("id", ""),
            "call_id": tc.get("id", ""),
            "name": func.get("name", ""),
            "arguments": func.get("arguments", "{}"),
        })
    
    if content_blocks:
        output.append({
            "type": "message",
            "id": data.get("id", "").replace("chatcmpl-", "msg_"),
            "role": "assistant",
            "content": content_blocks,
            "status": "completed",
        })
    
    # Usage
    usage = data.get("usage", {})
    
    return {
        "id": data.get("id", "").replace("chatcmpl-", "resp_"),
        "object": "response",
        "created_at": data.get("created", 0),
        "status": status,
        "model": model or data.get("model", ""),
        "output": output,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }
```

### 2.2 Streaming Response Translator

This is the most complex part. Must convert Chat Completions SSE chunks to
Responses API SSE events with sequence numbers.

```python
class ResponsesStreamTranslator:
    """Translates Chat Completions SSE chunks to Responses API SSE events."""
    
    def __init__(self, model: str = ""):
        self.model = model
        self.seq = 0
        self.started = False
        self.response_id = ""
        self.created = 0
        self.full_text = ""
        self.tool_calls = {}  # index → {id, name, arguments}
    
    def next_seq(self) -> int:
        self.seq += 1
        return self.seq
    
    def emit(self, event_type: str, data: dict) -> dict:
        data["sequence_number"] = self.next_seq()
        return {"event": event_type, "data": data}
    
    def translate_chunk(self, chunk: dict) -> list[dict]:
        """Translate a single Chat Completions chunk to Responses API events."""
        events = []
        
        if not chunk.get("choices"):
            return events
        
        choice = chunk["choices"][0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")
        
        # Start events (emit once)
        if not self.started:
            self.started = True
            self.response_id = f"resp_{chunk.get('id', 'unknown')}"
            self.created = chunk.get("created", 0)
            
            events.append(self.emit("response.created", {
                "type": "response.created",
                "response": {
                    "id": self.response_id,
                    "object": "response",
                    "created_at": self.created,
                    "status": "in_progress",
                    "output": [],
                },
            }))
            
            events.append(self.emit("response.in_progress", {
                "type": "response.in_progress",
                "response": {"id": self.response_id, "status": "in_progress"},
            }))
        
        # Text content delta
        if delta.get("content"):
            if not hasattr(self, '_output_item_added'):
                self._output_item_added = True
                events.append(self.emit("response.output_item.added", {
                    "type": "response.output_item.added",
                    "output_index": 0,
                    "item": {"type": "message", "role": "assistant", "content": []},
                }))
                events.append(self.emit("response.content_part.added", {
                    "type": "response.content_part.added",
                    "output_index": 0,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": ""},
                }))
            
            self.full_text += delta["content"]
            events.append(self.emit("response.output_text.delta", {
                "type": "response.output_text.delta",
                "output_index": 0,
                "content_index": 0,
                "delta": delta["content"],
            }))
        
        # Tool calls
        for tc in delta.get("tool_calls", []):
            idx = tc.get("index", 0)
            func = tc.get("function", {})
            
            if idx not in self.tool_calls:
                self.tool_calls[idx] = {"id": tc.get("id", ""), "name": "", "arguments": ""}
            
            if func.get("name"):
                self.tool_calls[idx]["name"] = func["name"]
            if func.get("arguments"):
                self.tool_calls[idx]["arguments"] += func["arguments"]
        
        # Finish
        if finish_reason:
            events.extend(self._flush_finish(finish_reason, chunk))
        
        return events
    
    def _flush_finish(self, finish_reason: str, chunk: dict) -> list[dict]:
        """Emit completion events."""
        events = []
        
        # Flush text output
        if self.full_text and hasattr(self, '_output_item_added'):
            events.append(self.emit("response.output_text.done", {
                "type": "response.output_text.done",
                "output_index": 0,
                "content_index": 0,
                "text": self.full_text,
            }))
            events.append(self.emit("response.content_part.done", {
                "type": "response.content_part.done",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": self.full_text},
            }))
            events.append(self.emit("response.output_item.done", {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": self.full_text}],
                    "status": "completed",
                },
            }))
        
        # Flush tool calls
        for idx in sorted(self.tool_calls.keys()):
            tc = self.tool_calls[idx]
            events.append(self.emit("response.output_item.done", {
                "type": "response.output_item.done",
                "output_index": len(self.tool_calls) + (1 if self.full_text else 0),
                "item": {
                    "type": "function_call",
                    "id": tc["id"],
                    "call_id": tc["id"],
                    "name": tc["name"],
                    "arguments": tc["arguments"],
                    "status": "completed",
                },
            }))
        
        # Final completed event
        usage = chunk.get("usage", {})
        events.append(self.emit("response.completed", {
            "type": "response.completed",
            "response": {
                "id": self.response_id,
                "object": "response",
                "created_at": self.created,
                "status": "completed",
                "model": self.model,
                "output": [],
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            },
        }))
        
        return events
```

---

## Phase 3 — Backend: Add `/v1/responses` Route

**File:** `backend/app/routers/v1_proxy.py`

```python
@router.post("/responses")
async def responses(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """OpenAI Responses API proxy.
    
    Accepts Responses API format and translates to/from Chat Completions
    for upstream providers.
    """
    from app.services.responses_translator import (
        responses_to_chat_completions,
        chat_completions_to_responses,
        ResponsesStreamTranslator,
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
    
    # Translate Responses API → Chat Completions
    chat_body = responses_to_chat_completions(body)
    
    # Resolve model to upstream targets
    targets = await resolve_model_to_targets(db, model, stream)
    if not targets:
        raise HTTPException(status_code=503, detail=f"No provider available for model: {model}")
    
    strategy, sticky_limit = await get_combo_strategy(db)
    targets = _get_rotated_targets(targets, model, strategy, sticky_limit)
    
    last_error = None
    for target in targets:
        forward_body = {**chat_body, "model": target.model, "stream": stream}
        
        try:
            if stream:
                return await _stream_responses(target, forward_body, request_id, model)
            else:
                return await _non_stream_responses(target, forward_body, request_id, model)
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


async def _non_stream_responses(target, body, request_id, model):
    """Non-streaming: translate response to Responses API format."""
    from app.services.responses_translator import chat_completions_to_responses
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(target.url, json=body, headers=target.headers)
        resp.raise_for_status()
        data = resp.json()
    
    result = chat_completions_to_responses(data, model)
    return JSONResponse(status_code=200, content=result, headers={"X-Request-Id": request_id})


async def _stream_responses(target, body, request_id, model):
    """Streaming: translate Chat Completions SSE to Responses API SSE."""
    from app.services.responses_translator import ResponsesStreamTranslator
    
    translator = ResponsesStreamTranslator(model=model)
    
    async def generate():
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream("POST", target.url, json=body, headers=target.headers) as resp:
                    resp.raise_for_status()
                    buffer = ""
                    async for chunk in resp.aiter_text():
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                continue
                            try:
                                chunk_data = json.loads(data_str)
                                events = translator.translate_chunk(chunk_data)
                                for event in events:
                                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Request-Id": request_id},
    )
```

---

## Phase 4 — Frontend: No Changes Required

The `/v1/responses` endpoint is a pure API endpoint. No UI changes needed.

---

## Phase 5 — Testing

### 5.1 Manual curl tests

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — Basic Responses API (non-streaming):**
```bash
curl -s -X POST http://localhost:9000/v1/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "instructions": "You are a helpful assistant.",
    "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Say hello in one word."}]}]
  }' | jq '{id, status, output_types: [.output[].type], text: .output[0].content[0].text}'
```
Expected: `status: "completed"`, `output_types: ["message"]`, text contains greeting.

**Test 2 — String input (shorthand):**
```bash
curl -s -X POST http://localhost:9000/v1/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "instructions": "Be brief.",
    "input": "What is 2+2?"
  }' | jq '{status, text: .output[0].content[0].text}'
```

**Test 3 — Streaming:**
```bash
curl -s -X POST http://localhost:9000/v1/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "input": "Say hello.",
    "stream": true
  }' | head -30
```
Expected: SSE events starting with `event: response.created`.

**Test 4 — With tools:**
```bash
curl -s -X POST http://localhost:9000/v1/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "What is the weather in Tokyo?"}]}],
    "tools": [{"type": "function", "name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}]
  }' | jq '{status, output_types: [.output[].type]}'
```
Expected: `output_types` includes `"function_call"`.

**Test 5 — Missing model (400):**
```bash
curl -s -X POST http://localhost:9000/v1/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello"}' | jq .
```
Expected: `400` with `"Missing required field: model"`.

### 5.2 Regression check

```bash
# Existing chat completions still works
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'

# Existing responses (if already ported) still works
curl -s -X POST http://localhost:9000/v1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "an/claude-sonnet-4", "max_tokens": 50, "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.content[0].text'
```

---

## Phase 6 — Report

1. **`docs/porting-status.md`** — Move `POST /v1/responses` to "Fully Ported".
2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 9 as ✅.
3. **`docs/plans/v1-responses.md`** (this file) — Update status to `Done`.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Streaming complexity | Responses API SSE has 8+ event types with sequence numbers. Must correctly handle `response.created`, `response.output_item.added`, `response.content_part.added`, `response.output_text.delta`, etc. |
| Reasoning/thinking content | `reasoning` items in input are buffered and attached as `reasoning_content` to the next assistant message. Some providers (xiaomi-mimo) use this for thinking mode. |
| Tool call streaming | Chat Completions streams tool call arguments incrementally. Responses API expects complete `function_call` items. Must accumulate arguments before emitting. |
| `call_id` length limit | Responses API enforces max 64 chars on `call_id`. Must clamp. |
| `input` as string | Responses API accepts `input` as a plain string (shorthand for single user message). Must handle both string and array. |
| Empty input | Empty `input: []` would produce empty `messages: []` which all providers reject. Must inject placeholder. |
| `previous_response_id` | Responses API supports conversation chaining via `previous_response_id`. Not supported in Phase 1. |
| `store` parameter | Responses API has `store` param for persistence. Not supported — ignored. |
| `/v1/responses/compact` | Original has a compact endpoint for conversation compression. Not ported in Phase 1. |
| Hosted tools | Responses API supports "hosted" tools like `request_user_input` without explicit `name`. Filtered out in translation. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/responses_translator.py` | NEW — Request + response translators, streaming translator |
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/responses` handler |
| `docs/porting-status.md` | Move responses endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 9 done |
| `docs/plans/v1-responses.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Route handler | Low | Same pattern as messages/chat_completions |
| Request translation | Medium | input[] → messages[], instructions → system, function_call → tool_calls |
| Non-streaming response | Medium | Build output[] with message + function_call items |
| Streaming response | High | 8+ SSE event types, sequence numbers, tool call accumulation |
| Reasoning handling | Medium | Buffer reasoning items, attach to next assistant message |
| Tool call streaming | High | Must accumulate partial arguments before emitting complete function_call |
| call_id clamping | Trivial | String truncation to 64 chars |

**Overall:** High complexity — the streaming response translator is the hardest
part. The request translator is medium complexity (similar to `/v1/messages`).
The non-streaming response translator is straightforward.

**Recommended implementation order:**
1. Request translator (Responses API → Chat Completions)
2. Non-streaming response translator (Chat Completions → Responses API JSON)
3. Route handler (non-streaming only)
4. Streaming response translator (Chat Completions SSE → Responses API SSE)
5. Streaming route handler
