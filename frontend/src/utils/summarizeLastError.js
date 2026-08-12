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

function stripHtmlLine(s) {
  return s.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

function plainTextFirstLine(s) {
  const first = s.split(/\r?\n/)[0] ?? s
  return stripHtmlLine(first)
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
    candidate = plainTextFirstLine(s)
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
