import { useState, useEffect, useCallback } from 'react'
import {
  Plus,
  Trash2,
  Copy,
  Pencil,
  ArrowUp,
  ArrowDown,
  X,
  Layers,
  Shuffle,
  Check,
  Search,
  Keyboard,
} from 'lucide-react'
import Card, { CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import ModelSelectModal from '../components/ModelSelectModal'
import { combosApi } from '../api/combos'
import { settingsApi } from '../api/settings'
import useCatalogStore from '../stores/catalogStore'

const NAME_RE = /^[a-zA-Z0-9_.\-]+$/
const MAX_VISIBLE_MODELS = 3

export default function CombosPage() {
  const [combos, setCombos] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingCombo, setEditingCombo] = useState(null)
  const [deletingCombo, setDeletingCombo] = useState(null)
  const [copiedId, setCopiedId] = useState(null)
  const [comboStrategies, setComboStrategies] = useState({})

  const fetchCombos = useCallback(async () => {
    try {
      const [combosRes, settingsRes] = await Promise.all([
        combosApi.getCombos(),
        settingsApi.get(),
      ])
      // Only LLM combos — media combos (kind set) have their own page
      setCombos((combosRes.data || []).filter(c => !c.kind))
      setComboStrategies(settingsRes.data?.comboStrategies || {})
    } catch (err) {
      console.error('Failed to fetch combos:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCombos()
  }, [fetchCombos])

  const handleCreate = () => {
    setEditingCombo(null)
    setShowForm(true)
  }

  const handleEdit = (combo) => {
    setEditingCombo(combo)
    setShowForm(true)
  }

  const handleSave = async (formData) => {
    try {
      if (editingCombo) {
        await combosApi.updateCombo(editingCombo.id, formData)
      } else {
        await combosApi.createCombo(formData)
      }
      setShowForm(false)
      setEditingCombo(null)
      await fetchCombos()
    } catch (err) {
      console.error('Failed to save combo:', err)
      throw err
    }
  }

  const handleDelete = async () => {
    if (!deletingCombo) return
    try {
      await combosApi.deleteCombo(deletingCombo.id)
      setDeletingCombo(null)
      await fetchCombos()
    } catch (err) {
      console.error('Failed to delete combo:', err)
    }
  }

  const handleCopyName = (combo) => {
    const text = combo.name
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    setCopiedId(combo.id)
    setTimeout(() => setCopiedId(null), 1500)
  }

  const handleComboStrategyChange = async (comboName, strategy) => {
    try {
      const updated = { ...comboStrategies }
      if (strategy && strategy !== 'fallback') {
        updated[comboName] = { fallbackStrategy: strategy, stickyRoundRobinLimit: 3 }
      } else {
        delete updated[comboName]
      }
      await settingsApi.update({ comboStrategies: updated })
      setComboStrategies(updated)
    } catch (err) {
      console.error('Failed to update combo strategy:', err)
    }
  }

  const handleStickyLimitChange = async (comboName, value) => {
    try {
      const updated = { ...comboStrategies }
      const current = updated[comboName] || {}
      updated[comboName] = { ...current, stickyRoundRobinLimit: Number(value) || 3 }
      await settingsApi.update({ comboStrategies: updated })
      setComboStrategies(updated)
    } catch (err) {
      console.error('Failed to update combo sticky limit:', err)
    }
  }

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-7 w-32 rounded bg-zinc-800 animate-pulse" />
            <div className="h-4 w-48 rounded bg-zinc-800 animate-pulse mt-2" />
          </div>
          <div className="h-9 w-32 rounded-lg bg-zinc-800 animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-zinc-700/50 bg-zinc-900/80 p-5 space-y-4 animate-pulse"
            >
              <div className="h-5 w-3/4 rounded bg-zinc-800" />
              <div className="flex gap-2">
                <div className="h-6 w-20 rounded-full bg-zinc-800" />
                <div className="h-6 w-24 rounded-full bg-zinc-800" />
                <div className="h-6 w-16 rounded-full bg-zinc-800" />
              </div>
              <div className="h-4 w-1/2 rounded bg-zinc-800" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Combos</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {combos.length} combo{combos.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus size={16} />
          Create Combo
        </Button>
      </div>

      {/* Combo list */}
      {combos.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
          <div className="w-16 h-16 rounded-2xl bg-blue-600/20 flex items-center justify-center mb-6">
            <Layers size={28} className="text-blue-400" />
          </div>
          <h2 className="text-xl font-semibold text-zinc-100 mb-2">
            No combos yet
          </h2>
          <p className="text-zinc-400 mb-6 max-w-md">
            Create your first combo to group models together for round-robin routing.
          </p>
          <Button onClick={handleCreate}>
            <Plus size={16} />
            Create Combo
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {combos.map((combo) => (
            <ComboCard
              key={combo.id}
              combo={combo}
              onEdit={() => handleEdit(combo)}
              onDelete={() => setDeletingCombo(combo)}
              onCopy={() => handleCopyName(combo)}
              copied={copiedId === combo.id}
              strategy={comboStrategies[combo.name]?.fallbackStrategy || 'fallback'}
              stickyLimit={comboStrategies[combo.name]?.stickyRoundRobinLimit ?? 3}
              onStrategyChange={(strategy) => handleComboStrategyChange(combo.name, strategy)}
              onStickyLimitChange={(value) => handleStickyLimitChange(combo.name, value)}
            />
          ))}
        </div>
      )}

      {/* Create/Edit Form Modal */}
      {showForm && (
        <ComboFormModal
          combo={editingCombo}
          onSave={handleSave}
          onClose={() => {
            setShowForm(false)
            setEditingCombo(null)
          }}
        />
      )}

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deletingCombo}
        onClose={() => setDeletingCombo(null)}
        title="Delete Combo"
      >
        <div className="space-y-4">
          <p className="text-sm text-zinc-300">
            Are you sure you want to delete{' '}
            <span className="font-mono font-semibold text-zinc-100">
              {deletingCombo?.name}
            </span>
            ? This action cannot be undone.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setDeletingCombo(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete}>
              <Trash2 size={14} />
              Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

/* -------------------------------------------------- */
/* ComboCard                                          */
/* -------------------------------------------------- */

function ComboCard({ combo, onEdit, onDelete, onCopy, copied, strategy, stickyLimit, onStrategyChange, onStickyLimitChange }) {
  const visibleModels = combo.models.slice(0, MAX_VISIBLE_MODELS)
  const overflowCount = combo.models.length - MAX_VISIBLE_MODELS

  return (
    <Card className="hover:border-zinc-600/80 transition-colors group">
      <CardContent className="p-5 space-y-3">
        {/* Combo name + kind badge */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3
              className="text-sm font-semibold text-zinc-100 font-mono truncate"
              title={combo.name}
            >
              {combo.name}
            </h3>
            {combo.kind && (
              <Badge variant="info" size="sm" className="mt-1">
                {combo.kind}
              </Badge>
            )}
          </div>
        </div>

        {/* Model tags */}
        {combo.models.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {visibleModels.map((model) => {
              const alias = model.includes('/') ? model.split('/')[0] : null
              const provider = alias ? useCatalogStore.getState().getProviderByAlias(alias) : null
              const shortName = model.includes('/') ? model.split('/').slice(1).join('/') : model
              return (
                <span
                  key={model}
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-800 text-zinc-300 border border-zinc-700/50"
                >
                  {provider && (
                    <span
                      className="inline-flex items-center justify-center w-4 h-4 rounded-sm text-[8px] font-bold"
                      style={{
                        backgroundColor: (provider.color || '#71717a') + '20',
                        color: provider.color || '#71717a',
                      }}
                    >
                      {provider.textIcon || alias.slice(0, 2).toUpperCase()}
                    </span>
                  )}
                  {shortName}
                </span>
              )
            })}
            {overflowCount > 0 && (
              <Badge variant="default" size="sm">
                +{overflowCount} more
              </Badge>
            )}
          </div>
        ) : (
          <p className="text-xs text-zinc-500 italic">No models configured</p>
        )}

        {/* Strategy selector + sticky limit */}
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shuffle size={14} className="text-zinc-500" />
              <span className="text-xs text-zinc-400">Strategy</span>
            </div>
            <select
              value={strategy}
              onChange={(e) => onStrategyChange(e.target.value)}
              className="px-2 py-1 text-xs border border-zinc-700 rounded-md bg-zinc-800/50 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              <option value="fallback">Fallback</option>
              <option value="round-robin">Round Robin</option>
              <option value="random">Random</option>
            </select>
          </div>
          {strategy === 'round-robin' && (
            <div className="flex items-center gap-2 pl-6">
              <span className="text-xs text-zinc-500">Sticky</span>
              <input
                type="number"
                min={1}
                max={100}
                value={stickyLimit}
                onChange={(e) => onStickyLimitChange(e.target.value)}
                className="w-16 px-2 py-1 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-200 focus:outline-none focus:border-zinc-500"
              />
              <span className="text-xs text-zinc-500">req/model</span>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center justify-end gap-1 pt-1 border-t border-zinc-800">
          <button
            onClick={onCopy}
            className="p-2 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors cursor-pointer"
            title="Copy combo name"
          >
            {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          </button>
          <button
            onClick={onEdit}
            className="p-2 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors cursor-pointer"
            title="Edit combo"
          >
            <Pencil size={14} />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-600/20 transition-colors cursor-pointer"
            title="Delete combo"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </CardContent>
    </Card>
  )
}

/* -------------------------------------------------- */
/* ComboFormModal (create / edit)                     */
/* -------------------------------------------------- */

function ComboFormModal({ combo, onSave, onClose }) {
  const [name, setName] = useState(combo?.name || '')
  const [kind, setKind] = useState(combo?.kind || '')
  const [models, setModels] = useState(combo?.models || [])
  const [newModel, setNewModel] = useState('')
  const [editingIndex, setEditingIndex] = useState(null)
  const [editingValue, setEditingValue] = useState('')
  const [nameError, setNameError] = useState('')
  const [saving, setSaving] = useState(false)
  const [showModelPicker, setShowModelPicker] = useState(false)
  const [showManualInput, setShowManualInput] = useState(false)

  // Validate name on change
  const handleNameChange = (val) => {
    setName(val)
    if (val && !NAME_RE.test(val)) {
      setNameError('Only letters, numbers, -, _, and . are allowed')
    } else {
      setNameError('')
    }
  }

  // Add models from the picker (array of model IDs)
  const handlePickerAdd = (modelIds) => {
    setModels((prev) => {
      const existing = new Set(prev)
      const fresh = modelIds.filter((id) => !existing.has(id))
      return [...prev, ...fresh]
    })
  }

  // Add a model from manual text input
  const addModel = () => {
    const trimmed = newModel.trim()
    if (!trimmed) return
    if (models.includes(trimmed)) return
    setModels((prev) => [...prev, trimmed])
    setNewModel('')
  }

  // Remove a model by index
  const removeModel = (idx) => {
    setModels((prev) => prev.filter((_, i) => i !== idx))
  }

  // Move model up in the list
  const moveUp = (idx) => {
    if (idx === 0) return
    setModels((prev) => {
      const next = [...prev]
      ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
      return next
    })
  }

  // Move model down in the list
  const moveDown = (idx) => {
    setModels((prev) => {
      if (idx >= prev.length - 1) return prev
      const next = [...prev]
      ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
      return next
    })
  }

  // Start inline editing a model name
  const startEdit = (idx) => {
    setEditingIndex(idx)
    setEditingValue(models[idx])
  }

  // Commit inline model name edit
  const commitEdit = () => {
    const trimmed = editingValue.trim()
    if (trimmed && trimmed !== models[editingIndex]) {
      setModels((prev) => prev.map((m, i) => (i === editingIndex ? trimmed : m)))
    }
    setEditingIndex(null)
    setEditingValue('')
  }

  // Submit the form
  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || nameError) return

    setSaving(true)
    try {
      await onSave({
        name: name.trim(),
        kind: kind.trim() || null,
        models,
      })
    } catch {
      // Error handled by caller
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={combo ? 'Edit Combo' : 'Create Combo'}
      className="max-w-xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name input */}
        <Input
          label="Combo Name"
          placeholder="e.g. gpt4-round-robin"
          value={name}
          onChange={(e) => handleNameChange(e.target.value)}
          error={nameError}
        />

        {/* Kind input (optional) */}
        <Input
          label="Kind (optional)"
          placeholder="e.g. webSearch, tts, image"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        />

        {/* Models list */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-1.5">
            Models
          </label>

          {/* Existing models */}
          {models.length > 0 && (
            <div className="space-y-1.5 mb-3 max-h-52 overflow-y-auto pr-1">
              {models.map((model, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 rounded-lg bg-zinc-800/50 border border-zinc-700/50 px-3 py-2 group/item"
                >
                  {/* Reorder buttons */}
                  <div className="flex flex-col -space-y-0.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => moveUp(idx)}
                      disabled={idx === 0}
                      className="p-0.5 rounded text-zinc-500 hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    >
                      <ArrowUp size={12} />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveDown(idx)}
                      disabled={idx === models.length - 1}
                      className="p-0.5 rounded text-zinc-500 hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    >
                      <ArrowDown size={12} />
                    </button>
                  </div>

                  {/* Model name or inline edit */}
                  {editingIndex === idx ? (
                    <input
                      type="text"
                      value={editingValue}
                      onChange={(e) => setEditingValue(e.target.value)}
                      onBlur={commitEdit}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitEdit()
                        if (e.key === 'Escape') {
                          setEditingIndex(null)
                          setEditingValue('')
                        }
                      }}
                      autoFocus
                      className="flex-1 min-w-0 bg-transparent text-sm text-zinc-100 font-mono outline-none border-b border-primary-500"
                    />
                  ) : (
                    <span
                      className="flex-1 min-w-0 text-sm text-zinc-200 font-mono truncate cursor-text flex items-center gap-2"
                      onClick={() => startEdit(idx)}
                      title="Click to edit"
                    >
                      {model.includes('/') && (() => {
                        const alias = model.split('/')[0]
                        const provider = useCatalogStore.getState().getProviderByAlias(alias)
                        if (provider) {
                          return (
                            <span
                              className="inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0"
                              style={{
                                backgroundColor: (provider.color || '#71717a') + '20',
                                color: provider.color || '#71717a',
                              }}
                            >
                              {provider.textIcon || alias.slice(0, 2).toUpperCase()}
                            </span>
                          )
                        }
                        return null
                      })()}
                      {model.includes('/') ? model.split('/').slice(1).join('/') : model}
                    </span>
                  )}

                  {/* Remove button */}
                  <button
                    type="button"
                    onClick={() => removeModel(idx)}
                    className="p-1 rounded text-zinc-600 hover:text-red-400 hover:bg-red-600/10 transition-colors cursor-pointer opacity-0 group-hover/item:opacity-100"
                    title="Remove model"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add model actions */}
          <div className="flex gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowModelPicker(true)}
            >
              <Search size={14} />
              Browse Models
            </Button>
            <button
              type="button"
              onClick={() => setShowManualInput((v) => !v)}
              className="px-3 py-2 rounded-lg text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <Keyboard size={13} />
              {showManualInput ? 'Hide manual' : 'Manual input'}
            </button>
          </div>

          {/* Manual input (hidden by default) */}
          {showManualInput && (
            <div className="flex gap-2 mt-2">
              <input
                type="text"
                value={newModel}
                onChange={(e) => setNewModel(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addModel()
                  }
                }}
                placeholder="Type model ID and press Enter"
                className="flex-1 rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent hover:border-zinc-600"
              />
              <Button
                type="button"
                variant="secondary"
                onClick={addModel}
                disabled={!newModel.trim()}
              >
                <Plus size={14} />
                Add
              </Button>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={!name.trim() || !!nameError || saving}
          >
            {saving ? 'Saving...' : combo ? 'Save Changes' : 'Create Combo'}
          </Button>
        </div>
      </form>

      {/* Model Picker Modal */}
      <ModelSelectModal
        isOpen={showModelPicker}
        onClose={() => setShowModelPicker(false)}
        onAdd={handlePickerAdd}
        existingModels={models}
      />
    </Modal>
  )
}
