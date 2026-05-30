import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Button from '../ui/Button'
import Badge from '../ui/Badge'
import { providersApi } from '../../api/providers'
import { useNotificationStore } from '../../stores/notificationStore'

/**
 * AddOpenAICompatibleModal — create a custom OpenAI-compatible provider node.
 *
 * Matches the original Next.js AddOpenAICompatibleModal:
 * - Name, Prefix, API Type (Chat/Responses), Base URL fields
 * - Optional API Key + Model ID for validation
 * - Validation via POST /provider-nodes/validate
 * - Form reset on successful submit
 * - Toast notifications on success/error
 */
export default function AddOpenAICompatibleModal({ isOpen, onClose, onCreated }) {
  const [formData, setFormData] = useState({
    name: '', prefix: '', apiType: 'chat', baseUrl: 'https://api.openai.com/v1',
  })
  const [submitting, setSubmitting] = useState(false)
  const [checkKey, setCheckKey] = useState('')
  const [checkModelId, setCheckModelId] = useState('')
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState(null)

  const addNotification = useNotificationStore(s => s.addNotification)

  const apiTypeOptions = [
    { value: 'chat', label: 'Chat Completions' },
    { value: 'responses', label: 'Responses API' },
  ]

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setFormData({ name: '', prefix: '', apiType: 'chat', baseUrl: 'https://api.openai.com/v1' })
      setCheckKey('')
      setCheckModelId('')
      setValidationResult(null)
    }
  }, [isOpen])

  // Reset baseUrl when apiType changes (matches original behavior)
  useEffect(() => {
    const defaultBaseUrl = 'https://api.openai.com/v1'
    setFormData(prev => ({ ...prev, baseUrl: defaultBaseUrl }))
  }, [formData.apiType])

  const handleSubmit = async () => {
    if (!formData.name.trim() || !formData.prefix.trim() || !formData.baseUrl.trim()) return
    setSubmitting(true)
    try {
      const res = await providersApi.createProviderNode({
        name: formData.name,
        prefix: formData.prefix,
        api_type: formData.apiType,
        base_url: formData.baseUrl,
        type: 'openai-compatible',
      })
      const node = res.data?.node || res.data
      onCreated(node)
      // Reset form on success
      setFormData({ name: '', prefix: '', apiType: 'chat', baseUrl: 'https://api.openai.com/v1' })
      setCheckKey('')
      setCheckModelId('')
      setValidationResult(null)
      addNotification({ type: 'success', message: 'Compatible provider created' })
    } catch (err) {
      console.error('Error creating OpenAI Compatible node:', err)
      addNotification({ type: 'error', message: 'Failed to create compatible provider' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleValidate = async () => {
    setValidating(true)
    try {
      const res = await providersApi.validateProviderNode({
        baseUrl: formData.baseUrl,
        apiKey: checkKey,
        type: 'openai-compatible',
        modelId: checkModelId.trim() || undefined,
      })
      setValidationResult(res.data)
    } catch {
      setValidationResult({ valid: false, error: 'Network error' })
    } finally {
      setValidating(false)
    }
  }

  const renderValidationResult = () => {
    if (!validationResult) return null
    const { valid, error, method } = validationResult

    if (valid) {
      return (
        <>
          <Badge variant="success">Valid</Badge>
          {method === 'chat' && (
            <span className="text-sm text-zinc-500">(via inference test)</span>
          )}
        </>
      )
    }
    return (
      <div className="flex flex-col gap-1">
        <Badge variant="danger">Invalid</Badge>
        {error && <span className="text-sm text-red-400">{error}</span>}
      </div>
    )
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add OpenAI Compatible">
      <div className="flex flex-col gap-4">
        <Input
          label="Name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="OpenAI Compatible (Prod)"
          hint="Required. A friendly label for this node."
        />
        <Input
          label="Prefix"
          value={formData.prefix}
          onChange={(e) => setFormData({ ...formData, prefix: e.target.value })}
          placeholder="oc-prod"
          hint="Required. Used as the provider prefix for model IDs."
        />
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-1.5">API Type</label>
          <select
            value={formData.apiType}
            onChange={(e) => setFormData({ ...formData, apiType: e.target.value })}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {apiTypeOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <Input
          label="Base URL"
          value={formData.baseUrl}
          onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
          placeholder="https://api.openai.com/v1"
          hint="Use the base URL (ending in /v1) for your OpenAI-compatible API."
        />
        <Input
          label="API Key (for Check)"
          type="password"
          value={checkKey}
          onChange={(e) => setCheckKey(e.target.value)}
        />
        <Input
          label="Model ID (optional)"
          value={checkModelId}
          onChange={(e) => setCheckModelId(e.target.value)}
          placeholder="e.g. gpt-4, claude-3-opus"
          hint="If provider lacks /models endpoint, enter a model ID to validate via chat/completions instead."
        />
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            onClick={handleValidate}
            disabled={!checkKey || validating || !formData.baseUrl.trim()}
          >
            {validating ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
            {validating ? 'Checking...' : 'Check'}
          </Button>
          {renderValidationResult()}
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleSubmit}
            className="flex-1"
            disabled={!formData.name.trim() || !formData.prefix.trim() || !formData.baseUrl.trim() || submitting}
          >
            {submitting ? <><Loader2 size={14} className="animate-spin mr-1" /> Creating...</> : 'Create'}
          </Button>
          <Button onClick={onClose} variant="ghost" className="flex-1">Cancel</Button>
        </div>
      </div>
    </Modal>
  )
}
