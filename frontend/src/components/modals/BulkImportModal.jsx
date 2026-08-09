import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import { oauthApi } from '../../api/oauth'

const FARM_PLACEHOLDER = `[
  {
    "email": "user@example.com",
    "tokens": {
      "access_token": "eyJ...",
      "refresh_token": "...",
      "expires_at": "2026-08-08T02:54:43Z"
    }
  }
]`

const API_KEYS_PLACEHOLDER = `sk-abcdef1234567890
sk-0987654321zyxwvu|Work account
sk-abcdef0987654321:Personal
[{"api_key": "sk-xxx", "name": "acct1"}, {"api_key": "sk-yyy"}]`

function normalizeToArray(parsed) {
  if (Array.isArray(parsed)) return parsed
  if (parsed && typeof parsed === 'object') {
    if (Array.isArray(parsed.accounts)) return parsed.accounts
    return [parsed]
  }
  return null
}

export default function BulkImportModal({
  isOpen,
  providerId,
  providerName = '',
  format = 'farm-json',
  onClose,
  onSuccess,
}) {
  const isApiKeys = format === 'api-keys'
  const [jsonText, setJsonText] = useState('')
  const [replace, setReplace] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const fileRef = useRef(null)

  const handleClose = () => {
    if (submitting) return
    setJsonText('')
    setReplace(false)
    setError('')
    setResult(null)
    onClose()
  }

  const handleFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setJsonText(String(reader.result || ''))
    reader.readAsText(file)
    e.target.value = ''
  }

  const handleSubmit = async () => {
    setError('')
    setResult(null)
    const trimmed = jsonText.trim()
    if (!trimmed) return

    let accounts
    if (isApiKeys) {
      // Try JSON first (array of objects with api_key/apiKey/key),
      // fall back to plain-text lines.
      try {
        accounts = normalizeToArray(JSON.parse(trimmed))
      } catch {
        accounts = trimmed
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean)
      }
    } else {
      try {
        accounts = normalizeToArray(JSON.parse(trimmed))
      } catch (err) {
        setError(`Invalid JSON: ${err.message}`)
        return
      }
    }
    if (!accounts || accounts.length === 0) {
      setError(
        isApiKeys ? 'No API keys found in input' : 'No accounts found in input'
      )
      return
    }

    setSubmitting(true)
    try {
      const res = await oauthApi.bulkImport(providerId, accounts, replace)
      setResult(res.data)
      const changed = (res.data.created || 0) + (res.data.updated || 0)
      if (changed > 0 && onSuccess) onSuccess()
    } catch (err) {
      setError(
        err.response?.data?.detail || err.message || 'Request failed'
      )
    } finally {
      setSubmitting(false)
    }
  }

  const problemItems =
    result?.results?.filter(
      (r) => r.status !== 'created' && r.status !== 'updated'
    ) || []

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={`Bulk Import ${providerName}`.trim()}
      className="max-w-2xl"
    >
      <div className="flex flex-col gap-4">
        <p className="text-xs text-zinc-400">
          {isApiKeys
            ? 'Paste API keys one per line — format: key or key|name — ' +
              'or upload a .txt/.json file. Existing keys are skipped ' +
              'unless replace is enabled.'
            : 'Paste a grok-farm-modular JSON export (array of accounts ' +
              'with email + tokens), or upload the .json file. Accounts ' +
              'with an expired token are skipped.'}
        </p>

        <textarea
          className="w-full rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-sm font-mono resize-y min-h-[220px] text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
          placeholder={isApiKeys ? API_KEYS_PLACEHOLDER : FARM_PLACEHOLDER}
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          disabled={submitting}
        />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              className="rounded border-zinc-600 bg-zinc-800 accent-primary-500"
              checked={replace}
              onChange={(e) => setReplace(e.target.checked)}
              disabled={submitting}
            />
            {isApiKeys
              ? 'Replace existing (upsert by API key)'
              : 'Replace existing (upsert by email)'}
          </label>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => fileRef.current?.click()}
            disabled={submitting}
          >
            <Upload size={14} className="mr-1" />
            {isApiKeys ? 'Upload File' : 'Upload JSON File'}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept={
              isApiKeys
                ? '.txt,.json,text/plain,application/json'
                : '.json,application/json'
            }
            className="hidden"
            onChange={handleFile}
          />
        </div>

        {error && (
          <p className="text-xs text-red-400 break-words">{error}</p>
        )}

        {result && (
          <div className="flex flex-col gap-2">
            <div className="text-sm text-zinc-200">
              <span className="text-green-400">
                {result.created || 0} created
              </span>
              {', '}
              <span className="text-blue-400">
                {result.updated || 0} updated
              </span>
              {', '}
              <span className="text-yellow-400">
                {result.skipped || 0} skipped
              </span>
              {', '}
              <span
                className={
                  result.failed > 0 ? 'text-red-400' : 'text-zinc-500'
                }
              >
                {result.failed || 0} failed
              </span>
            </div>
            {problemItems.length > 0 && (
              <ul className="rounded-lg border border-zinc-700/50 bg-zinc-950 p-2 text-xs font-mono max-h-40 overflow-y-auto">
                {problemItems.map((item) => (
                  <li key={item.index} className="text-yellow-400">
                    [{item.index}]{' '}
                    {item.email || item.name
                      ? `${item.email || item.name}: `
                      : ''}
                    {item.status}
                    {item.error ? ` — ${item.error}` : ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="flex gap-2">
          <Button
            onClick={handleSubmit}
            fullWidth
            disabled={submitting || !jsonText.trim()}
          >
            {submitting ? 'Importing...' : 'Import All'}
          </Button>
          <Button
            onClick={handleClose}
            variant="ghost"
            fullWidth
            disabled={submitting}
          >
            Close
          </Button>
        </div>
      </div>
    </Modal>
  )
}
