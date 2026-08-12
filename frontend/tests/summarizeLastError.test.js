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

  it('extracts message from truncated JSON', () => {
    const raw = '{"error":{"message":"Rate limit exceeded for gpt-4...'
    assert.equal(
      summarizeLastError(raw),
      'Rate limit exceeded for gpt-4...',
    )
  })

  it('strips crude HTML and takes first line', () => {
    const raw = '<html><body><p>Gateway timeout</p></body></html>'
    const out = summarizeLastError(raw)
    assert.match(out, /Gateway timeout/i)
    assert.ok(!out.includes('<'))
  })

  it('extracts text from HTML split across newlines', () => {
    const raw = '<html>\n<body><p>Gateway timeout</p>'
    const out = summarizeLastError(raw)
    assert.match(out, /Gateway timeout/i)
    assert.ok(!out.includes('<'))
  })

  it('uses first line only for multiline plain text', () => {
    const raw = 'Gateway timeout\nupstream diagnostics'
    assert.equal(summarizeLastError(raw), 'Gateway timeout')
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
