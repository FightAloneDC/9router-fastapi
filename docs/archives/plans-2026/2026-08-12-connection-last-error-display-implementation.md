# Connection Last Error Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a human-readable one-line last error on each connection row, with click-to-open full raw `lastError` and Copy.

**Architecture:** Pure frontend util `summarizeLastError` extracts a short message from raw upstream text/JSON. `ConnectionRow` on `ProviderDetailPage` shows the summary under badges and opens the existing `Modal` for full detail + copy via `copyToClipboard`. No backend changes.

**Tech Stack:** React 19, existing `Modal` + `copyToClipboard`, Node.js built-in test runner (`node --test`) for the pure util (no Vitest in repo).

**Spec:** `docs/plans/2026-08-12-connection-last-error-display-design.md`

## Global Constraints

- Code/docs English; chat with user Indonesian.
- No new DB columns; no backend API changes for v1.
- No per-provider error parsers (PS Rule / YAGNI).
- No hover-only as the sole detail path.
- Do not put truncated raw JSON beside `#priority`.
- Surgical edits to `ProviderDetailPage.jsx`; prefer a small util file.
- Do not auto-push; do not claim UI done without build/manual check notes.
- Commit steps are for plan execution when the user authorizes implementation — not for drive-by commits.

## File map

| File | Responsibility |
|------|----------------|
| `frontend/src/utils/summarizeLastError.js` | Generic summary + optional relative-time helper |
| `frontend/tests/summarizeLastError.test.js` | Node `--test` cases for summarizer |
| `frontend/src/pages/ProviderDetailPage.jsx` | Wire summary line + Last Error modal in `ConnectionRow` |

---

### Task 1: `summarizeLastError` util + tests

**Files:**
- Create: `frontend/src/utils/summarizeLastError.js`
- Create: `frontend/tests/summarizeLastError.test.js`

**Interfaces:**
- Produces:
  - `summarizeLastError(raw: unknown, maxLen?: number): string`
    — default `maxLen = 72`; empty/whitespace → `''`
  - `formatLastErrorAgo(iso: unknown, nowMs?: number): string`
    — relative label like `2h ago`, or `''` if invalid

- [ ] **Step 1: Write failing tests**

Create `frontend/tests/summarizeLastError.test.js`:

```javascript
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  formatLastErrorAgo,
  summarizeLastError,
} from '../src/utils/summarizeLastError.js'

describe('summarizeLastError', () => {
  it('returns empty for null/empty', () => {
    assert.equal(summarizeLastError(null), '')
    assert.equal(summarizeLastError(''), '')
    assert.equal(summarizeLastError('   '), '')
  })

  it('extracts error.message from JSON object string', () => {
    const raw = JSON.stringify({
      error: { message: 'Rate limit exceeded', type: 'rate_limit' },
    })
    assert.equal(summarizeLastError(raw), 'Rate limit exceeded')
  })

  it('extracts top-level message', () => {
    const raw = JSON.stringify({ message: 'Invalid API key' })
    assert.equal(summarizeLastError(raw), 'Invalid API key')
  })

  it('extracts string error field', () => {
    const raw = JSON.stringify({ error: 'upstream failed' })
    assert.equal(summarizeLastError(raw), 'upstream failed')
  })

  it('strips crude HTML and takes first line', () => {
    const raw = '<html><body><p>Gateway timeout</p></body></html>'
    const out = summarizeLastError(raw)
    assert.match(out, /Gateway timeout/i)
    assert.ok(!out.includes('<'))
  })

  it('truncates long plain text at maxLen with ellipsis', () => {
    const raw = 'x'.repeat(100)
    const out = summarizeLastError(raw, 40)
    assert.ok(out.length <= 41)
    assert.ok(out.endsWith('…') || out.endsWith('...'))
  })

  it('keeps useful HTTP-ish prefix when present', () => {
    const raw = '429: {"error":{"message":"Too many requests"}}'
    // Either parse nested after strip, or keep 429 + message —
    // must mention too many / 429, not dump full JSON braces noise
    const out = summarizeLastError(raw)
    assert.ok(
      /429|too many/i.test(out),
      `unexpected summary: ${out}`,
    )
    assert.ok(!out.includes('{"error"'))
  })
})

describe('formatLastErrorAgo', () => {
  it('returns empty for invalid', () => {
    assert.equal(formatLastErrorAgo(null), '')
    assert.equal(formatLastErrorAgo('nope'), '')
  })

  it('formats hours ago', () => {
    const now = Date.parse('2026-08-12T12:00:00.000Z')
    const iso = '2026-08-12T10:00:00.000Z'
    assert.equal(formatLastErrorAgo(iso, now), '2h ago')
  })
})
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd frontend && node --test tests/summarizeLastError.test.js
```

Expected: FAIL (module missing).

- [ ] **Step 3: Implement util**

Create `frontend/src/utils/summarizeLastError.js`:

```javascript
/**
 * Generic lastError summarizer for connection rows.
 * No provider-specific branches.
 */

const DEFAULT_MAX = 72

function truncateAtWord(text, maxLen) {
  const t = text.replace(/\s+/g, ' ').trim()
  if (t.length <= maxLen) return t
  const slice = t.slice(0, maxLen - 1)
  const sp = slice.lastIndexOf(' ')
  const base = sp > maxLen * 0.5 ? slice.slice(0, sp) : slice
  return `${base}…`
}

function pickFromObject(obj) {
  if (!obj || typeof obj !== 'object') return ''
  const err = obj.error
  if (err && typeof err === 'object' && typeof err.message === 'string') {
    return err.message.trim()
  }
  if (typeof obj.message === 'string') return obj.message.trim()
  if (typeof err === 'string') return err.trim()
  if (typeof obj.detail === 'string') return obj.detail.trim()
  return ''
}

function stripHtml(s) {
  return s.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

/**
 * @param {unknown} raw
 * @param {number} [maxLen]
 * @returns {string}
 */
export function summarizeLastError(raw, maxLen = DEFAULT_MAX) {
  if (raw == null) return ''
  const s = String(raw).trim()
  if (!s) return ''

  let candidate = ''

  // JSON object / array-wrapped
  if (s.startsWith('{') || s.startsWith('[')) {
    try {
      const parsed = JSON.parse(s)
      candidate = pickFromObject(
        Array.isArray(parsed) ? parsed[0] : parsed,
      )
    } catch {
      // fall through
    }
  }

  // Leading "429: {json}" style
  if (!candidate) {
    const m = s.match(/^(\d{3})\s*:\s*([\s\S]+)$/)
    if (m) {
      const status = m[1]
      const rest = m[2].trim()
      let inner = ''
      if (rest.startsWith('{')) {
        try {
          inner = pickFromObject(JSON.parse(rest))
        } catch {
          inner = ''
        }
      }
      candidate = inner ? `${status}: ${inner}` : `${status}: ${rest}`
    }
  }

  if (!candidate) {
    candidate = stripHtml(s).split(/\n/)[0] || stripHtml(s)
  }

  return truncateAtWord(candidate, maxLen)
}

/**
 * @param {unknown} iso
 * @param {number} [nowMs]
 * @returns {string}
 */
export function formatLastErrorAgo(iso, nowMs = Date.now()) {
  if (iso == null || iso === '') return ''
  const t = Date.parse(String(iso))
  if (Number.isNaN(t)) return ''
  const sec = Math.max(0, Math.floor((nowMs - t) / 1000))
  if (sec < 60) return 'just now'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 48) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  return `${day}d ago`
}
```

Adjust implementation if a test expectation is slightly off — keep behavior aligned with the design (no raw JSON dump in summary).

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd frontend && node --test tests/summarizeLastError.test.js
```

Expected: all tests pass.

- [ ] **Step 5: Commit** (when execution authorized)

```bash
git add frontend/src/utils/summarizeLastError.js \
  frontend/tests/summarizeLastError.test.js
git commit -m "feat(providers): add generic lastError summarizer"
```

---

### Task 2: Wire summary line + Last Error modal in `ConnectionRow`

**Files:**
- Modify: `frontend/src/pages/ProviderDetailPage.jsx` (`ConnectionRow` ~117–320)

**Interfaces:**
- Consumes: `summarizeLastError`, `formatLastErrorAgo` from util; `Modal`; `copyToClipboard` (already imported on page — pass in or import in row scope)
- Produces: visible summary when `lastError` present; modal with full text + Copy

Field access note: payload exposes `lastError` / `lastErrorAt` (and sometimes snake_case). Prefer:

```javascript
const lastError =
  connection.lastError ||
  connection.last_error ||
  providerSpecific.lastError ||
  ''
const lastErrorAt =
  connection.lastErrorAt ||
  connection.last_error_at ||
  providerSpecific.lastErrorAt ||
  null
```

- [ ] **Step 1: Import helpers near top of `ProviderDetailPage.jsx`**

```javascript
import {
  formatLastErrorAgo,
  summarizeLastError,
} from '../utils/summarizeLastError'
```

`Modal` and `copyToClipboard` are already used on this page — reuse them.

- [ ] **Step 2: Add local state inside `ConnectionRow`**

```javascript
  const [showLastError, setShowLastError] = useState(false)
  const [copiedError, setCopiedError] = useState(false)

  const lastError =
    connection.lastError ||
    connection.last_error ||
    providerSpecific.lastError ||
    ''
  const lastErrorAt =
    connection.lastErrorAt ||
    connection.last_error_at ||
    providerSpecific.lastErrorAt ||
    null
  const errorSummary = summarizeLastError(lastError)
  const errorAgo = formatLastErrorAgo(lastErrorAt)
```

- [ ] **Step 3: Render summary under badge row (not beside `#priority`)**

After the badge flex row (and after proxy subtitle if any), when `errorSummary`:

```jsx
  {errorSummary && (
    <button
      type="button"
      onClick={() => setShowLastError(true)}
      className="mt-1 max-w-full text-left text-[11px] text-red-400/90 hover:text-red-300 truncate"
      title="View full last error"
    >
      <span className="truncate">{errorSummary}</span>
      {errorAgo ? (
        <span className="text-zinc-500"> · {errorAgo}</span>
      ) : null}
    </button>
  )}
```

Keep on the left column under the name/badges (same `flex-1 min-w-0` block). Do **not** insert raw `lastError` next to `#priority`.

- [ ] **Step 4: Modal for full error**

Reuse page `Modal` (import already present at ConfirmModal pattern — `Modal` is imported). Inside `ConnectionRow` return fragment or wrap:

```jsx
  <Modal
    isOpen={showLastError}
    onClose={() => setShowLastError(false)}
    title="Last error"
    className="max-w-2xl"
  >
    <div className="space-y-3 px-6 pb-6">
      {lastErrorAt && (
        <p className="text-xs text-zinc-500">
          {new Date(lastErrorAt).toLocaleString()}
          {errorAgo ? ` (${errorAgo})` : ''}
        </p>
      )}
      {errorSummary && (
        <p className="text-sm text-zinc-300">{errorSummary}</p>
      )}
      <pre className="max-h-64 overflow-auto rounded-md border border-zinc-700 bg-zinc-950 p-3 text-[11px] text-zinc-300 whitespace-pre-wrap break-all">
        {String(lastError)}
      </pre>
      <div className="flex justify-end gap-2">
        <Button
          size="sm"
          variant="secondary"
          onClick={async () => {
            const ok = await copyToClipboard(String(lastError))
            if (ok) {
              setCopiedError(true)
              setTimeout(() => setCopiedError(false), 1500)
            }
          }}
        >
          {copiedError ? 'Copied' : 'Copy full error'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setShowLastError(false)}
        >
          Close
        </Button>
      </div>
    </div>
  </Modal>
```

Ensure `ConnectionRow` return is wrapped in `<>...</>` if needed so Modal can sit beside the row root.

Match existing `Button` / `Modal` import usage on the page. If `Modal` children already include padding via parent patterns, adjust spacing to avoid double padding — inspect `ConfirmModal` / other in-file modals and mirror.

- [ ] **Step 5: Manual / build check**

```bash
# Prefer docker frontend if host node_modules missing
docker compose -f docker-compose.dev.yml exec frontend npm run build
# or from frontend/: npm run build
```

Manual on `/providers/:id` with a connection that has `lastError`:
1. Summary visible without hover
2. Click opens modal with full text
3. Copy works
4. No raw JSON next to `#priority`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ProviderDetailPage.jsx
git commit -m "feat(providers): show last error summary and copyable detail"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Human summary ~72 chars | 1–2 |
| Generic JSON/HTML/fallback extract | 1 |
| Relative `lastErrorAt` on row | 1–2 |
| Click detail (not hover-only) | 2 |
| Full raw + Copy | 2 |
| Show even if inactive | 2 (no `isActive` gate on summary) |
| No raw JSON by priority | 2 |
| No backend / no PS parsers | — |

## Placeholder / consistency review

- No TBD.
- Field names cover camelCase + snake_case + `providerSpecific`.
- Util API names match Task 2 imports.
