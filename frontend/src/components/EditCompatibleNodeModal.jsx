import { useState, useEffect } from 'react'
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import Modal from './ui/Modal'
import Input from './ui/Input'
import Button from './ui/Button'
import Badge from './ui/Badge'

/**
 * EditCompatibleNodeModal — edit settings for an OpenAI/Anthropic-compatible provider node.
 *
 * Matches the original Next.js EditCompatibleNodeModal component:
 * - Name, Prefix, API Type (OpenAI only), Base URL fields
 * - Inline "Test Connection" section with API key + optional model ID
 * - Validation via POST /provider-nodes/validate
 *
 * @param {boolean} isOpen
 * @param {Object|null} node - Provider node object { id, name, prefix, api_type, base_url }
 * @param {Function} onSave - async (formData) => void, formData has { name, prefix, base_url, api_type? }
 * @param {Function} onClose
 * @param {boolean} isAnthropic - Whether this is an Anthropic-compatible node
 */
export default function EditCompatibleNodeModal({ isOpen, node, onSave, onClose, isAnthropic }) {
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [prefix, setPrefix] = useState('')
  const [apiType, setApiType] = useState('chat')
  const [saving, setSaving] = useState(false)
  const [checkKey, setCheckKey] = useState('')
  const [checkModelId, setCheckModelId] = useState('')
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState(null)

  useEffect(() => {
    if (isOpen && node) {
      setName(node.name || '')
      setBaseUrl(node.base_url || (isAnthropic ? 'https://api.anthropic.com/v1' : 'https://api.openai.com/v1'))
      setPrefix(node.prefix || '')
      setApiType(node.api_type || 'chat')
    }
  }, [isOpen, node, isAnthropic])

  useEffect(() => {
    if (!isOpen) {
      setValidationResult(null)
      setCheckKey('')
      setCheckModelId('')
    }
  }, [isOpen])

  const canSave = name.trim() && prefix.trim() && baseUrl.trim()

  const handleSave = async () => {
    if (!canSave) return
    setSaving(true)
    try {
      const payload = { name: name.trim(), base_url: baseUrl.trim(), prefix: prefix.trim() }
      if (!isAnthropic) payload.api_type = apiType
      await onSave(payload)
    } finally {
      setSaving(false)
    }
  }

  const handleValidate = async () => {
    setValidating(true)
    setValidationResult(null)
    try {
      const { default: client } = await import('../api/client')
      const res = await client.post('/provider-nodes/validate', {
        baseUrl: baseUrl.trim(),
        apiKey: checkKey,
        type: isAnthropic ? 'anthropic-compatible' : 'openai-compatible',
        modelId: checkModelId.trim() || undefined,
      })
      setValidationResult(res.data.valid ? 'success' : 'failed')
    } catch {
      setValidationResult('failed')
    } finally {
      setValidating(false)
    }
  }

  if (!node) return null

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Edit ${isAnthropic ? 'Anthropic' : 'OpenAI'} Compatible`}>
      <div className="flex flex-col gap-4">
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder={`${isAnthropic ? 'Anthropic' : 'OpenAI'} Compatible (Prod)`} />
        <p className="text-xs text-zinc-500 -mt-2">Required. A friendly label for this node.</p>

        <Input label="Prefix" value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder={isAnthropic ? 'ac-prod' : 'oc-prod'} />
        <p className="text-xs text-zinc-500 -mt-2">Required. Used as the provider prefix for model IDs.</p>

        {!isAnthropic && (
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">API Type</label>
            <select
              value={apiType}
              onChange={(e) => setApiType(e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors hover:border-zinc-600"
            >
              <option value="chat">Chat Completions</option>
              <option value="responses">Responses API</option>
            </select>
          </div>
        )}

        <Input label="Base URL" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder={isAnthropic ? 'https://api.anthropic.com/v1' : 'https://api.openai.com/v1'} />
        <p className="text-xs text-zinc-500 -mt-2">
          Use the base URL (ending in /v1) for your {isAnthropic ? 'Anthropic' : 'OpenAI'}-compatible API.
        </p>

        {/* Validate section */}
        <div className="border-t border-zinc-700/50 pt-4 mt-4">
          <p className="text-xs text-zinc-400 mb-3 font-medium">Test Connection</p>
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Input label="API Key (for Check)" type="password" value={checkKey} onChange={(e) => setCheckKey(e.target.value)} />
            </div>
            <Button
              variant="secondary"
              onClick={handleValidate}
              disabled={!checkKey || validating || !baseUrl.trim()}
              className="mb-0.5"
            >
              {validating ? <><Loader2 size={14} className="animate-spin" /> Checking...</> : 'Check'}
            </Button>
          </div>
          <div className="mt-3">
            <Input label="Model ID (optional)" value={checkModelId} onChange={(e) => setCheckModelId(e.target.value)} placeholder="e.g. my-model-id" />
            <p className="text-xs text-zinc-500 mt-1">
              If provider lacks /models endpoint, enter a model ID to validate via chat/completions instead.
            </p>
          </div>
          {validationResult && (
            <div className="mt-3">
              <Badge variant={validationResult === 'success' ? 'success' : 'danger'}>
                {validationResult === 'success' ? <><CheckCircle2 size={12} className="mr-1" /> Valid</> : <><AlertCircle size={12} className="mr-1" /> Invalid</>}
              </Badge>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Button onClick={handleSave} disabled={!canSave || saving} className="flex-1">
            {saving ? <><Loader2 size={14} className="animate-spin" /> Saving...</> : 'Save'}
          </Button>
          <Button onClick={onClose} variant="ghost" className="flex-1">Cancel</Button>
        </div>
      </div>
    </Modal>
  )
}
