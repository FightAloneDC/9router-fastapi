import { useState } from 'react'
import { Plus, Download, Trash2, Copy, Check, FlaskConical, Loader2, Bot } from 'lucide-react'
import Button from './ui/Button'

function CompatibleModelRow({ modelId, fullModel, copied, onCopy, onDelete, onTest, testStatus, isTesting }) {
  const borderColor =
    testStatus === 'ok'
      ? 'border-emerald-500/40'
      : testStatus === 'error'
        ? 'border-red-500/40'
        : 'border-zinc-700'

  const iconColor =
    testStatus === 'ok'
      ? 'text-emerald-400'
      : testStatus === 'error'
        ? 'text-red-400'
        : 'text-zinc-500'

  return (
    <div className={`group flex items-center gap-3 p-3 rounded-lg border ${borderColor} hover:bg-zinc-800/30 transition-colors`}>
      <Bot size={16} className={`shrink-0 ${iconColor}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-zinc-200 truncate">{modelId}</p>
        <div className="flex items-center gap-1 mt-1">
          <code className="text-xs text-zinc-500 font-mono bg-zinc-800/80 px-1.5 py-0.5 rounded">{fullModel}</code>
          <button
            onClick={() => onCopy(fullModel, `model-${modelId}`)}
            className="p-0.5 opacity-0 group-hover:opacity-100 hover:bg-zinc-800 rounded text-zinc-500 hover:text-primary-400 transition-colors cursor-pointer"
            title="Copy"
          >
            {copied === `model-${modelId}` ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          </button>
          {onTest && (
            <button
              onClick={onTest}
              disabled={isTesting}
              className="p-0.5 opacity-0 group-hover:opacity-100 hover:bg-zinc-800 rounded text-zinc-500 hover:text-primary-400 transition-colors cursor-pointer disabled:opacity-50"
              title="Test"
            >
              {isTesting ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
            </button>
          )}
        </div>
      </div>
      <button
        onClick={onDelete}
        className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-500/10 rounded text-zinc-500 hover:text-red-400 transition-all cursor-pointer"
        title="Remove model"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

/**
 * CompatibleModelsSection — manage models for an OpenAI/Anthropic-compatible provider node.
 *
 * Uses the alias-based model storage pattern matching the original Next.js source:
 * - modelAliases: { [alias]: "providerPrefix/modelId" }
 * - onSetAlias(modelId, alias, providerStorageAlias): creates a model alias
 * - onDeleteAlias(alias): removes a model alias
 *
 * @param {string} providerStorageAlias - Provider prefix used for storage (e.g. "openai-compatible-chat-abc123")
 * @param {string} providerDisplayAlias - Provider prefix shown to users (e.g. "oc-prod")
 * @param {Object} modelAliases - Map of alias -> full model path
 * @param {string|null} copied - Currently copied model identifier
 * @param {Function} onCopy - Copy handler (text, id)
 * @param {Function} onSetAlias - Add model alias (modelId, alias, providerStorageAlias)
 * @param {Function} onDeleteAlias - Remove model alias (alias)
 * @param {Array} connections - Provider connections (for /models import)
 * @param {boolean} isAnthropic - Whether this is an Anthropic-compatible node
 */
export default function CompatibleModelsSection({
  providerStorageAlias,
  providerDisplayAlias,
  modelAliases,
  copied,
  onCopy,
  onSetAlias,
  onDeleteAlias,
  connections,
  isAnthropic,
}) {
  const [newModel, setNewModel] = useState('')
  const [adding, setAdding] = useState(false)
  const [importing, setImporting] = useState(false)
  const [testingModelId, setTestingModelId] = useState(null)
  const [modelTestResults, setModelTestResults] = useState({})

  const handleTestModel = async (modelId) => {
    if (testingModelId) return
    setTestingModelId(modelId)
    try {
      const { default: client } = await import('../api/client')
      const res = await client.post('/models/test', { model: `${providerStorageAlias}/${modelId}` })
      setModelTestResults((prev) => ({ ...prev, [modelId]: res.data?.ok ? 'ok' : 'error' }))
    } catch {
      setModelTestResults((prev) => ({ ...prev, [modelId]: 'error' }))
    } finally {
      setTestingModelId(null)
    }
  }

  const providerAliases = Object.entries(modelAliases).filter(
    ([, model]) => model.startsWith(`${providerStorageAlias}/`)
  )

  const allModels = providerAliases.map(([alias, fullModel]) => ({
    modelId: fullModel.replace(`${providerStorageAlias}/`, ''),
    fullModel,
    alias,
  }))

  const generateDefaultAlias = (modelId) => {
    const parts = modelId.split('/')
    return parts[parts.length - 1]
  }

  const resolveAlias = (modelId) => {
    const fullModel = `${providerStorageAlias}/${modelId}`
    if (Object.values(modelAliases).includes(fullModel)) return null
    const baseAlias = generateDefaultAlias(modelId)
    if (!modelAliases[baseAlias]) return baseAlias
    const prefixedAlias = `${providerDisplayAlias}-${baseAlias}`
    if (!modelAliases[prefixedAlias]) return prefixedAlias
    return null
  }

  const handleAdd = async () => {
    if (!newModel.trim() || adding) return
    const modelId = newModel.trim()
    const resolvedAlias = resolveAlias(modelId)
    if (!resolvedAlias) {
      alert('All suggested aliases already exist. Please choose a different model or remove conflicting aliases.')
      return
    }
    setAdding(true)
    try {
      await onSetAlias(modelId, resolvedAlias, providerStorageAlias)
      setNewModel('')
    } catch (error) {
      console.error('Error adding model:', error)
    } finally {
      setAdding(false)
    }
  }

  const handleImport = async () => {
    if (importing) return
    const activeConnection = connections.find((conn) => conn.is_active !== false)
    if (!activeConnection) return

    setImporting(true)
    try {
      const { default: client } = await import('../api/client')
      const res = await client.get(`/providers/${activeConnection.id}/models`)
      const models = res.data?.models || []
      if (models.length === 0) {
        alert('No models returned from /models.')
        return
      }
      let importedCount = 0
      for (const model of models) {
        const modelId = model.id || model.name || model.model
        if (!modelId) continue
        const resolvedAlias = resolveAlias(modelId)
        if (!resolvedAlias) continue
        await onSetAlias(modelId, resolvedAlias, providerStorageAlias)
        importedCount += 1
      }
      if (importedCount === 0) alert('No new models were added.')
    } catch (error) {
      console.error('Error importing models:', error)
      alert('Failed to import models. The /models endpoint may not be available.')
    } finally {
      setImporting(false)
    }
  }

  const canImport = connections.some((conn) => conn.is_active !== false)

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        Add {isAnthropic ? 'Anthropic' : 'OpenAI'}-compatible models manually or import them from the /models endpoint.
      </p>

      <div className="flex items-end gap-2 flex-wrap">
        <div className="flex-1 min-w-[240px]">
          <label className="text-xs text-zinc-500 mb-1 block">Model ID</label>
          <input
            type="text"
            value={newModel}
            onChange={(e) => setNewModel(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder={isAnthropic ? 'claude-3-opus-20240229' : 'gpt-4o'}
            className="w-full px-3 py-2 text-sm border border-zinc-700 rounded-lg bg-zinc-800/50 text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent font-mono"
          />
        </div>
        <Button size="sm" onClick={handleAdd} disabled={!newModel.trim() || adding}>
          {adding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          {adding ? 'Adding...' : 'Add'}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={handleImport}
          disabled={!canImport || importing}
        >
          {importing ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          {importing ? 'Importing...' : 'Import from /models'}
        </Button>
      </div>

      {!canImport && (
        <p className="text-xs text-zinc-500">Add a connection to enable importing models.</p>
      )}

      {allModels.length > 0 && (
        <div className="flex flex-col gap-2">
          {allModels.map(({ modelId, fullModel, alias }) => (
            <CompatibleModelRow
              key={fullModel}
              modelId={modelId}
              fullModel={`${providerDisplayAlias}/${modelId}`}
              copied={copied}
              onCopy={onCopy}
              onDelete={() => onDeleteAlias(alias)}
              onTest={connections.length > 0 ? () => handleTestModel(modelId) : undefined}
              testStatus={modelTestResults[modelId]}
              isTesting={testingModelId === modelId}
            />
          ))}
        </div>
      )}

      {allModels.length === 0 && (
        <p className="text-xs text-zinc-500 py-4 text-center">No models configured yet</p>
      )}
    </div>
  )
}
