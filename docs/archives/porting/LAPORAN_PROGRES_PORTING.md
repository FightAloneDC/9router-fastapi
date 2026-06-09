# Laporan Progres Porting 9Router ke FastAPI

Tanggal analisis: 2026-05-27

## Ringkasan Eksekutif

Porting 9Router dari backend Node.js/Next.js API routes ke Python FastAPI sudah mencapai tahap operasional untuk fungsi inti: autentikasi, dashboard utama, provider CRUD, model management, OAuth, proxy chat completions, embeddings, TTS, STT, audio voices, usage/quota/settings, proxy pools, MITM, CLI tools, console log, dan API keys.

Status saat ini bukan lagi "awal porting"; fondasi FastAPI + React sudah berjalan. Pekerjaan tersisa terutama berada di permukaan API `/v1/*` yang belum lengkap, penyelarasan detail provider/media dengan original Next.js, dan verifikasi integrasi provider berbayar yang membutuhkan kredensial.

Catatan penting: beberapa dokumen lama di `docs/features` dan `docs/archives` bertentangan dengan QA/audit yang lebih baru. Laporan ini memprioritaskan dokumen terkini berikut:
- `docs/porting-status.md`
- `docs/qa/QA-provider-restructure.md`
- `docs/audits/AUDIT-provider-restructure-VERIFIED.md`
- `docs/plans/*.md` dengan status dan implementation log terbaru

Dokumen arsip tetap dipakai untuk konteks gap historis, tetapi tidak dianggap final jika sudah dikoreksi oleh QA/verifikasi yang lebih baru.

## Pemetaan Terminologi Node.js ke FastAPI

| Node.js / Next.js original | FastAPI port | Catatan |
|---|---|---|
| Next.js API route `route.js` | `APIRouter` di `backend/app/routers/*` | Setiap route original dipetakan ke fungsi async FastAPI. |
| Express/Next middleware | FastAPI dependencies / Starlette middleware | Auth memakai dependency seperti `get_current_user()` dan API key validator. |
| Request body manual parsing | Pydantic schemas + FastAPI params | JSON memakai Pydantic; multipart memakai `UploadFile` + `Form`. |
| SQLite/local DB helper | SQLAlchemy async + PostgreSQL | Model ORM berada di `backend/app/models`. |
| npm packages | pip/uv packages | HTTP upstream memakai `httpx`; auth JWT memakai `python-jose`; bcrypt langsung. |
| Node `fetch` upstream | `httpx.AsyncClient` | Dipakai pada proxy, validation, TTS/STT/voice adapters. |
| Next.js server components | React 19 + Vite SPA | Frontend port tidak lagi server-rendered. |
| `src/shared/constants/providers.js` | `frontend/src/constants/providers.js` + `backend/app/routers/providers/constants.py` + `backend/app/services/proxy.py` | Konstanta provider wajib sinkron di frontend dan backend. |
| Cron/background worker | FastAPI lifespan/background loop | Token refresh ada di `services/token_refresh.py`. |
| WebSocket/log buffer original | FastAPI WebSocket router | Console log viewer ada di `routers/console.py`. |

## Arsitektur FastAPI yang Teridentifikasi

| Area | Modul FastAPI / React | Status |
|---|---|---|
| App factory, CORS, lifespan, router registration | `backend/app/main.py` | Selesai |
| Database | `database.py`, SQLAlchemy async, Alembic, PostgreSQL 16 | Selesai |
| Auth password + JWT | `routers/auth.py`, `services/auth.py`, `authStore.js` | Selesai |
| Provider CRUD modular | `routers/providers/connections.py` | Selesai |
| Provider models fetch/clear/type override | `routers/providers/models.py` | Selesai dengan follow-up kecil untuk konsistensi type storage |
| Provider validation/testing | `routers/providers/testing.py`, `validation.py` | Selesai untuk major LLM providers; media validators masih perlu dirapikan |
| Provider nodes/custom compatible | `routers/providers/nodes.py` | Selesai |
| Proxy resolver | `services/proxy.py` | Selesai untuk chat, embeddings, TTS/STT support parsers; perlu diperluas untuk search/fetch/images/messages/responses |
| v1 proxy routes | `routers/v1_proxy.py` | Selesai sebagian |
| OAuth providers | `routers/oauth.py`, `services/oauth.py`, `services/oauth_providers.py` | Selesai untuk flow utama |
| Media providers API | `routers/media_providers.py`, `MediaProvidersPage.jsx`, `MediaProviderDetailPage.jsx` | Selesai sebagian; UI modal/model management masih punya gap |
| Model aliases/custom/disabled/availability/test | `routers/models.py` | Selesai |
| Usage, quota, settings, MITM, CLI tools, proxy pools, console, API keys | router masing-masing | Selesai |

## Integrasi Provider yang Disebutkan

Provider yang disebut dalam dokumen terbagi menjadi:

| Kategori | Contoh provider | Status umum |
|---|---|---|
| Free/no auth | kiro, qwen, gemini-cli, opencode, edge-tts, local-device | Banyak sudah terdaftar; beberapa local/no-auth butuh service lokal atau dependency OS |
| Free tier API key | openrouter, nvidia, gemini, cloudflare-ai | Terdaftar; sebagian live test tergantung kredensial/quota |
| OAuth | claude, codex, github, cursor, kilocode, kiro | OAuth core sudah ported |
| API key LLM | openai, anthropic, deepseek, groq, mistral, cohere, fireworks, together, xai, perplexity, nebius, siliconflow, azure, vertex, bedrock, etc. | Core CRUD, validation, model fetch, chat routing sudah mayoritas ported |
| Web cookie | grok-web, perplexity-web | Tercatat sebagai manual/cookie auth |
| Custom compatible | openai-compatible, anthropic-compatible, custom embedding node | CRUD, validation, cascade delete selesai |
| Media/TTS/STT/Image/Search/Fetch | elevenlabs, deepgram, assemblyai, inworld, minimax, fal-ai, stability-ai, tavily, brave-search, exa, jina-reader, firecrawl, etc. | Sebagian route/adapters selesai; search/fetch/images masih pending |

## Daftar Plan yang Selesai (Done)

| Plan / fitur | Komponen FastAPI/React | Bukti dari docs | Catatan |
|---|---|---|---|
| Login & authentication | `routers/auth.py`, `services/auth.py`, `LoginPage.jsx`, Zustand `authStore` | `docs/features/01-authentication.md` status COMPLETE | Password-only login, JWT HS256 24 jam, default `123456`. |
| Dashboard shell dan 14 fase awal | React routes/pages, backend routers utama | `docs/archives/PROGRESS.md` | Arsip menyebut 14/14 fase dashboard selesai. |
| Provider CRUD | `routers/providers/connections.py` | `docs/porting-status.md`, provider matrix | Includes create/read/update/delete, sanitized client response. |
| Provider test/validation | `routers/providers/testing.py`, `validation.py` | `docs/porting-status.md`, provider matrix | Major validation types selesai: OpenAI, Anthropic, Google, Azure, Cloudflare, Vertex, Ollama, cookie/manual. |
| Provider models fetch/clear | `routers/providers/models.py` | `docs/porting-status.md`, QA fetch/clear archives | Fetch models dan clear models tersedia; gunakan `DELETE /providers/{conn_id}/models`. |
| Provider nodes/custom compatible | `routers/providers/nodes.py` | `docs/porting-status.md`, provider matrix | CRUD, validation, sync on update, cascade delete selesai. |
| Suggested models | `GET /providers/suggested-models` | `docs/porting-status.md`, provider matrix | Public suggested model fetcher tersedia. |
| Model alias/custom/disabled/availability/test | `routers/models.py` | `docs/features/media-providers.md`, provider matrix | Alias CRUD, disabled model, cooldown, test model tersedia. |
| v1 chat completions | `POST /v1/chat/completions` di `v1_proxy.py` | `docs/porting-status.md` | Core proxy routing selesai. |
| v1 models list query filter | `GET /v1/models?kind=...` | `docs/plans/v1-models-kind.md`, source check | Query-param kind filter ada; path alias `/v1/models/{kind}` masih pending. |
| v1 embeddings | `POST /v1/embeddings` | `docs/plans/v1-embeddings.md` | Done dan live-tested; Gemini embeddings custom URL masih follow-up. |
| Embedding UI/playground follow-up | `MediaProviderDetailPage.jsx` | `docs/plans/v1-embeddings-frontend.md`, `fix-media-provider-detail-filter.md` | Real API call, model filtering per kind, endpoint routing, clipboard fallback selesai. |
| v1 audio speech/TTS backend | `POST /v1/audio/speech`, `services/tts_adapters.py` | `docs/plans/v1-audio-speech.md` | Backend feature-complete; Gemini live-tested. Banyak provider berbayar masih butuh live test. |
| v1 audio transcriptions/STT sebagian besar | `POST /v1/audio/transcriptions`, `services/stt_adapters.py` | `docs/plans/v1-audio-transcriptions.md` | 4 provider live-verified: Groq, Gemini, Deepgram, AssemblyAI. OpenAI/HF/Azure pending credentials. |
| v1 audio voices | `GET /v1/audio/voices`, `services/voice_fetchers.py` | `docs/plans/v1-audio-voices.md` | 4 provider live-verified: gemini, deepgram, edge-tts, local-device-empty. Paid providers deferred. |
| Media provider listing API | `GET /media-providers`, `GET /media-providers/{kind}` | `docs/qa/QA-provider-restructure.md` | 10 endpoints return 200; 9 service kinds present. |
| Provider list kind filtering | `GET /providers?kind=...` | `docs/qa/QA-provider-restructure.md` | LLM/media filtering API lulus QA. |
| Model type system | model entries `{id,name,type}`, `infer_model_type`, overrides | `docs/qa/QA-provider-restructure.md`, audit verified | Model type field dan PATCH type override tersedia. |
| Swagger auth fix | `/auth/token`, HTTPBearer/OAuth2-compatible flow | `docs/plans/fix-swagger-auth.md` | Status Done; Swagger bisa dipakai untuk API testing. |
| OAuth flows | `routers/oauth.py`, `services/oauth.py`, `oauth_providers.py` | `docs/porting-status.md` | Kiro, Cursor, GitHub, Codex, GitLab/import flows tercatat. |
| Combos, usage, quota, settings, MITM, CLI tools, proxy pools, console, API keys | Router masing-masing | `docs/porting-status.md`, `PROGRESS.md` | Ported sebagai modul dashboard/backend. |
| Kilo Gateway integration | provider constants, proxy alias, model fetch/test | `docs/archives/plan-kilo-provider-integration.md`, QA Kilo archives | Core jalan, tapi ada bug validasi key invalid pada audit lama. |

## Daftar Plan yang Belum Selesai (Pending/In-Progress)

| Plan / fitur | Status | Dampak | Instruksi lanjut |
|---|---|---|---|
| `POST /v1/images/generations` | Pending | Image generation API belum OpenAI-compatible di FastAPI | Port adapters sesuai `docs/plans/v1-images-generations.md`. |
| `POST /v1/search` | Pending | Web search unified endpoint belum tersedia | Implement provider-as-model pattern dan normalizer. |
| `POST /v1/web/fetch` | Pending | URL extraction/fetch unified endpoint belum tersedia | Implement Firecrawl/Jina/Tavily/Exa adapters bertahap. |
| `POST /v1/messages` | Pending | Anthropic-compatible public endpoint belum lengkap | Butuh route dan translator Claude <-> OpenAI, bukan sekadar pass-through. |
| `POST /v1/responses` | Pending | OpenAI Responses API belum lengkap | Butuh request/response translator dan SSE event conversion. |
| `GET /v1/models/{kind}` | Pending | CLI/external clients yang memakai path slug belum kompatibel | Tambah route sebelum catch-all `/models/{model_path:path}`. |
| `GET /v1/models/info` | Pending/optional | Metadata model detail belum tersedia | Bisa dikerjakan setelah path kind route. |
| Gemini embeddings custom URL | Pending follow-up | Gemini embeddings tidak akan jalan via generic `/embeddings` path | Implement `embedContent`/provider-specific URL builder. |
| ProviderDetailPage crash | Pending critical bug | `/providers/:providerId` blank pada QA, memblokir provider detail/model management | Reproduksi browser, perbaiki exception, lalu verifikasi badges/model management. |
| MediaProviderDetailPage AddKeyModal & available models | Pending | Add API Key media bisa salah validasi `Base URL is required`; model UI belum setara LLM page | Ikuti `docs/plans/fix-media-provider-modal.md` phase 1-4. |
| Media provider validators | Pending | Provider TTS/STT/embedding memakai fallback `openai` jika `validationType` belum spesifik | Tambah validator untuk elevenlabs, deepgram, inworld, minimax, voyage, assemblyai, noauth. |
| Paid provider live testing | TODO - PENDING (PAID PROVIDER) | Tidak bisa diverifikasi tanpa kredensial/API key/quota | SKIP dulu; lanjut pekerjaan non-paid berikutnya. |
| TTS frontend playground | Pending optional | Backend TTS bisa dipakai via API, tetapi UI playback/download belum lengkap | Kerjakan setelah backend/API blockers selesai. |
| TTS local providers + AWS Polly | Pending/deferred | edge-tts/coqui/tortoise/google-tts/local-device/AWS Polly belum setara original | Local services dan AWS SigV4 butuh task tersendiri. |
| STT OpenAI/HuggingFace/Azure verification | Pending credentials | Adapter ada, live test belum lengkap | Tandai sebagai paid/credential-gated jika tidak ada key. |
| Audio voices ElevenLabs/Inworld/MiniMax verification | TODO - PENDING (PAID PROVIDER) | Voice fetchers ada, live test belum bisa tanpa paid keys | SKIP dulu. |
| Missing/partial providers vs original | Pending | Beberapa provider masih hilang atau alias/id tidak konsisten | Sinkronisasi backend `PROVIDER_DEFAULTS`, `PROVIDER_CONFIGS`, `ALIAS_TO_ID`, frontend constants. |
| OpenRouter backend `tts` serviceKinds | Pending dari audit verified | Backend tidak menampilkan OpenRouter sebagai TTS provider | Tambah `"tts"` di backend constants jika belum fixed. |
| 8 frontend serviceKinds mismatch | Pending dari audit verified | Provider muncul di tab media yang salah atau hilang | Sinkronkan anthropic, groq, mistral, perplexity, huggingface, together, cohere, xai dengan original. |
| Provider-specific model fetch stores plain strings on one path | Pending | Tipe model bisa hilang saat fetch via config path | Store `{id,type}` bukan string-only pada path yang tersisa. |
| `ProviderConnectionOut.serviceKinds` schema consistency | Pending | `GET /providers` bisa strip field meski helper mengisinya | Tambah `serviceKinds` ke schema atau samakan response behavior. |
| `/providers/{id}/test-models` | Pending/medium | Original endpoint tidak ada; workaround `POST /models/test` sudah ada | Port hanya jika UI/compat client membutuhkan. |
| `/providers/kilo/free-models` | Pending/low | Kilo-specific endpoint belum ada | Low priority. |
| Dashboard pages Basic Chat/Profile/Translator | Pending medium | Beberapa halaman original belum ada | Prioritaskan Basic Chat untuk QA manual jika diperlukan. |
| Backend auxiliary features | Pending low/medium | Tunnel, translator, MCP, tags, pricing, OIDC, version/update, shutdown, settings sub-endpoints, Vercel deploy proxy pools belum ported | Kerjakan setelah core proxy surface stabil. |
| Region-specific baseUrl/provider-specific fields | Pending | Azure/Xiaomi/region providers berisiko tidak identik dengan original | Audit AddKeyModal + constants terhadap `_reference`. |
| Usage provider constants | Pending | `USAGE_SUPPORTED_PROVIDERS` / `USAGE_APIKEY_PROVIDERS` belum setara original | Tambah jika usage/quota UI perlu provider-specific filtering. |

## Risiko dan Catatan Eksekusi

1. Provider data harus tetap di JSON blob `provider_connections.data`; jangan tambah kolom DB baru untuk data provider.
2. Setiap perubahan provider harus sinkron di tiga tempat: backend provider defaults, backend proxy alias/config, dan frontend constants.
3. Untuk area providers, selalu baca `_reference/` dulu sebelum implementasi agar perilaku tetap faithful terhadap original Next.js.
4. Jangan mengandalkan dokumen lama tanpa cross-check: beberapa status lama sudah berubah oleh QA terbaru.
5. Pengujian provider berbayar harus di-skip sampai kredensial tersedia. Jangan jadikan ini blocker untuk task non-paid.
6. Backend/frontend punya hot reload via Docker volume; perubahan kode tidak perlu rebuild kecuali dependency/container config berubah.
