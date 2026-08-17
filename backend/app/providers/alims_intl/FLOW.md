# Alibaba Studio (`alims-intl`) — provider flow

Source of truth: files in this folder. Sibling `alicode-intl` is
Coding Plan (different host/keys). This module is Model Studio
Intl with standard DashScope `sk-...` keys.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, `RATE_LIMITS`, notice |
| `models.py` | Fetch `/models` via shared header-auth helper |
| `handler.py` | Chat sanitize (developer→system); `execute_rerank` |
| `quota.py` | Summary tracker + on-demand model detail |
| `bulk.py` | Farm-json bulk import |

## Identity

```
PROVIDER_ID          = alims-intl
ALIAS                = alims-intl
BASE_URL             = https://dashscope-intl.aliyuncs.com/compatible-mode/v1
MODEL_CATALOG_TABLE  = True
SERVICE_KINDS        = llm, rerank, embedding, image, video, tts, stt
```

## Rate limits

`RATE_LIMITS` mirrors **Singapore / International** rows from Model
Studio rate-limit docs (local copy:
`.scratch/alibaba-studio-ratelimit.md`). Includes text, VL/omni,
third-party LLM, embedding, rerank, image, video, TTS, and STT.

- RPM+TPM when the docs publish both.
- RPM-only for image/video/TTS/STT that have no TPM column.
- Docs that list **RPS** are stored as **RPM = RPS × 60**.
- Temporary raises live in the Model Studio console Limits page.
- Docs URL: https://www.alibabacloud.com/help/en/model-studio/rate-limit

## Catalog

`MODEL_CATALOG_TABLE` is True. Rows in `provider_models`.
Fetch/clear do not write catalogs back into connection blobs.

## Quota tracker

`AlimsIntlUsageHandler` (`USES_UPSTREAM = False`):

1. **List / refresh (`fetch`)** — two account summary bars only
   (`requests (last 60s)`, `tokens (last 60s)`). Keeps
   `GET /quota` payloads small (~KB, not ~1 MB).
2. **Model details (`fetch_model_details`)** — full per-model
   RPM/TPM from `RATE_LIMITS` + local usage. Triggered by
   `GET /usage/{id}?detail=models`. **Not** written to
   `quota_cache`.
3. Optional `x-ratelimit-*` header observe stores only summary /
   last-model live rows (never the full catalog).

UI: Alibaba Studio card shows the summary bars; ListTree button
opens a searchable modal for the detail request.

## Chat / rerank

- `prepare_request`: map `developer` → `system`; drop invalid
  `reasoning_effort`.
- Rerank: DashScope compatible-mode `/reranks` via handler.
