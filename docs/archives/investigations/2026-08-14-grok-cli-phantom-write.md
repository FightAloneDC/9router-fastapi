# Grok CLI phantom write (tool-calling research)

**Date:** 2026-08-14  
**Scope:** Persist-to-file via Kimi Code + `gcli/grok-4.6` (and one `gcli/grok-4.5` session) through 9Router.  
**Not in scope:** Factual quality of the audit text the model writes.

## Question

When a user asks Grok (via grok-cli) to save work to a file, does the model
call `Write` / `Edit`, or does it finish with `stop` and claim the file exists?

Dashboard request logs were not enough: streaming grok saves `usage` as
`response_body`, and large JSON is truncated. Wire dumps under
`.scratch/grok-cli/` were added so every conclusion is from request/response
files, not from CLI paste alone.

## Method

1. Client: Kimi Code → `POST /v1/chat/completions` on host `:9000`.
2. Dump (opt-in): `{stamp}_{rid}_client.json` + `_response.json`.
   Retry inject writes `r1-…` / `r2-…`.
3. Success criterion for this research: a `Write` tool call whose `path` /
   `content` appear on disk. CLI text that says “file saved” is not enough.

Enable dumps in `backend/.env`:

```
GROK_CLI_DUMP=true
```

Uvicorn `--reload` does not watch `.env`. The dump gate re-reads `.env` on
each call and ignores commented lines (`# GROK_CLI_DUMP=true` is off).
Default is off. Inject/retry still runs when dumps are off.

## What the dumps showed

### The model can Write

Same connection that phantom-wrote an audit file later called `Write` for a
tiny task (`grok-test.txt` / `grok was here`). The account is not
“tool-calling disabled”.

### Long “save to file” tasks often close without a tool

Typical last turn:

- `finish_reason`: `stop`
- `tool_calls`: `[]`
- Non-empty `content` claiming `docs/….md` was written
- File missing on disk

This happened on **grok-4.6 and grok-4.5**, multiple accounts, with and
without MCP tools, `thinking=high` or unused effort on 4.6 (effort is not
forwarded for `grok-4.6*`). Thinking / MCP / one “bad account” were
rejected as the cause.

### Detector (when to retry)

Retry only if **all** hold:

1. Client advertised `Write` or `Edit`.
2. Some **user** message has persist intent (`simpan`/`tulis`/`save` +
   `file`/`dokumen` **or** a path with an extension, e.g.
   `simpan ke docs/FOO.md`).
3. This reply `finish_reason == stop`.
4. This reply did not call `Write` / `Edit` / `StrReplace`.
5. Assistant content is non-empty.
6. History has no prior `Write` / `Edit` / `StrReplace` (`fresh`).

`Bash` (e.g. `go test -race`) is **not** “already wrote the file”. Treating
it as such skipped retry (session v12).

Do **not** mark the whole connection as anomalous: the same account can
Write on the next turn.

### Inject (what we do)

On a hit, the first SSE is held. One (or more) upstream retry is sent with:

- The original Responses `input`
- A user nudge quoting the phantom sentence
- `tool_choice: required`

The client sees the retry stream (usually a `Write`). On HTTP 429 /
exhausted / other fallback errors, the same inject hops to the next
grok-cli connection (dumps `r1-`, `r2-`, …; max 8 hops). The first
request of a session that is already 429 still uses the existing outer
fallback loop.

Do not synthesize a `Write` from chat text. The prose is a summary, not
the file.

## Session log (root dumps + CLI)

| Session | Model | Outcome |
|---------|--------|---------|
| v1 | 4.6 | Phantom. `Write` in tools. Detector missed (intent regex). |
| v2 | 4.6, no MCP | Same phantom. |
| v3 | 4.6, stricter prompt | Same. Intent missed `simpan hasilnya ke file`. |
| v4 | 4.5 | Same phantom, other account. |
| v5 | 4.6, new `#1` account | Same. |
| v6 | 4.6, Random, high | 43 accounts, 0× Write on the close turn. |
| v7 | 4.6 | Audit phantom; follow-up `grok-test.txt` **Write OK**. |
| v8 | 4.6 | Phantom → retry `Write` → file on disk. |
| v9 | 4.6, natural prompt | Intent missed `simpan ke docs/….md`. No `r-*`. |
| v10 | 4.6 | Detect + retry, **429** on same account. No hop yet. |
| v11 | 4.6 | First conn 429 → other acc → phantom → `r1` **Write** → file. |
| v12 | 4.6 | Phantom; `Bash` in history blocked retry. File missing. |
| v13 | 4.6 | Phantom → `r1` **Write** → `docs/AUDIT_BUG_2026-08-14.md` on disk. |

Successful persist-via-inject: **v8, v11, v13**. Failures after the
detector/hop fixes were explained (regex, Bash, 429) and patched.

## Code

| Piece | Path |
|-------|------|
| Detector + inject body | `backend/app/providers/grok_cli/anomaly.py` |
| Stream buffer, retry, hop | `backend/app/routers/v1_proxy/chat.py` |
| File dump (gated) | `backend/app/providers/grok_cli/debug_dump.py` |
| Env | `GROK_CLI_DUMP`, optional `GROK_CLI_DUMP_DIR` |

## How to reproduce

1. `GROK_CLI_DUMP=true` in `backend/.env` (uncommented).
2. Host API `:9000`.
3. Kimi: `gcli/grok-4.6`, natural prompt such as:

   `Pelajari proyek ini, lalu audit potensi memory leak, resource leak, dan race condition. Hasil audit simpan ke docs/AUDIT_MEMORY_RACE_2026-08-14.md`

4. Expect: last real turn `stop` without `Write`, then `r1-*` with
   `tool_call_names: ["Write"]`, then the path on disk.
5. If the first account is exhausted, expect hop / `r2-*` or an initial
   429 then another connection.

## Conclusion

Grok CLI on this proxy **does** support `Write`. For long “save to a
file” tasks it often **chooses not to call the tool** and lies in prose.
A grok-cli-only, one-shot (or hopped) inject with `tool_choice=required`
recovers the tool call in the sessions we captured after the detector
matched. That was the research goal.

Content truth of the written file is a different problem and was not
part of this work.
