# Qoder Provider — Context for Next Session

## Summary

After investigation, the Qoder provider works correctly. The main issue was **stale proxy cache** when toggling connections — not broken tokens.

## Key Findings

1. **All 3 connections' tokens are valid** — userinfo returns 200, model list returns 200, chat returns 200.

2. **`cosy.py` is correct** — `build_cosy_headers()` produces exact same headers as qodercli v1.0.14 (byte-for-byte verified).

3. **`handler.py` is correct** — chat request body matches qodercli structure, WAF-bypass encoding works, model resolution works.

4. **The real bug was in `connections.py`** — `update_provider()` did not call `invalidate_connection_cache()` after DB update. This caused the proxy to use stale connection data (30-second TTL cache) when user toggled enable/disable.

5. **`pt-` tokens are PAT (Personal Access Tokens)** — they are NOT the same as `jt-` (job tokens) or `dt-` (device tokens). PAT cannot be used directly; must be exchanged via `/api/v1/jobToken/exchange`.

6. **Qoder uses TWO auth shapes:**
   - Some account/status/region endpoints use plain bearer/signature
   - `/algo` service endpoints like chat generation use `Authorization: Bearer COSY.{payloadB64}.{sig}`

   So `Bearer COSY` is NOT wrong for `/algo` endpoints.

7. Document `QODER_PROVIDER_DOC.md` has been corrected to state the facts above.

## File Status

- `QODER_PROVIDER_DOC.md` — updated with correct auth flow
- `backend/app/providers/qoder/constants.py` — IDE version 1.0.14, data policy "agree"
- `backend/app/providers/qoder/cosy.py` — major refactor (correct COSY signing)
- `backend/app/providers/qoder/handler.py` — validate_connection calls fetch_user_info
- `backend/tests/test_qoder_cosy.py` — unit tests (4 tests pass)
- `backups/qoder-provider-backup-20260609-163719.tar.gz` — backup before changes

## Before Starting

Run a quick audit:

```bash
git status --short
git diff -- backend/app/providers/qoder/
```

## Safe Debugging Steps (Read-Only)

If user asks to fix Qoder, use these read-only steps:

1. Compare old connection DB data vs new PAT connection data.
2. Test `fetch_qoder_catalog()` for failing and working connections.
3. Do not change auth flow PAT/OAuth without evidence.
4. If rollback is needed, use backup folder — do NOT reset entire repo.

## Do NOT

- Touch `cosy.py` or `handler.py` unless evidence shows they are wrong
- Change auth flow without reading `QODER_PROVIDER_DOC.md` first
- Reset git to old commits (will lose other work)
- Assume all connections are broken — test each one individually
