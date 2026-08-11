import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Search, X, Check, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import Badge from './ui/Badge'
import useCatalogStore from '../stores/catalogStore'
import client from '../api/client'

const TYPE_BADGE_STYLES = {
  llm: 'bg-emerald-500/15 text-emerald-400',
  embedding: 'bg-blue-500/15 text-blue-400',
  rerank: 'bg-indigo-500/15 text-indigo-400',
  tts: 'bg-purple-500/15 text-purple-400',
  stt: 'bg-orange-500/15 text-orange-400',
  image: 'bg-pink-500/15 text-pink-400',
  webSearch: 'bg-cyan-500/15 text-cyan-400',
  webFetch: 'bg-teal-500/15 text-teal-400',
  imageToText: 'bg-rose-500/15 text-rose-400',
  video: 'bg-amber-500/15 text-amber-400',
  music: 'bg-indigo-500/15 text-indigo-400',
}

export default function ModelSelectModal({ isOpen, onClose, onAdd, existingModels = [] }) {
  const [models, setModels] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(new Set())
  const [expandedProviders, setExpandedProviders] = useState(new Set())
  const searchRef = useRef(null)

  // Fetch all models when modal opens
  useEffect(() => {
    if (!isOpen) return
    useCatalogStore.getState().fetchCatalog()
    setLoading(true)
    setSelected(new Set())
    setSearch('')
    client
      .get('/v1/models')
      .then((res) => {
        const data = res.data?.data || []
        // Filter to only LLM models (combos are LLM-only)
        setModels(data.filter((m) => m.owned_by !== '9router'))
      })
      .catch((err) => {
        console.error('Failed to fetch models:', err)
        setModels([])
      })
      .finally(() => setLoading(false))
  }, [isOpen])

  // Focus search on open
  useEffect(() => {
    if (isOpen && searchRef.current) {
      setTimeout(() => searchRef.current?.focus(), 100)
    }
  }, [isOpen])

  // Group models by provider
  const grouped = useMemo(() => {
    const groups = {}
    for (const m of models) {
      const alias = m.owned_by || 'unknown'
      if (!groups[alias]) groups[alias] = []
      groups[alias].push(m)
    }
    // Sort models within each group
    for (const alias of Object.keys(groups)) {
      groups[alias].sort((a, b) => a.id.localeCompare(b.id))
    }
    return groups
  }, [models])

  // Provider display order: sort by name
  const providerOrder = useMemo(() => {
    return Object.keys(grouped).sort((a, b) => {
      const pa = useCatalogStore.getState().getProviderByAlias(a)
      const pb = useCatalogStore.getState().getProviderByAlias(b)
      const na = pa?.name || a
      const nb = pb?.name || b
      return na.localeCompare(nb)
    })
  }, [grouped])

  // Filtered groups
  const filteredGroups = useMemo(() => {
    if (!search.trim()) return grouped
    const q = search.toLowerCase()
    const result = {}
    for (const [alias, providerModels] of Object.entries(grouped)) {
      const provider = useCatalogStore.getState().getProviderByAlias(alias)
      const providerName = (provider?.name || alias).toLowerCase()
      const matchedModels = providerModels.filter(
        (m) =>
          m.id.toLowerCase().includes(q) ||
          providerName.includes(q)
      )
      if (matchedModels.length > 0) result[alias] = matchedModels
    }
    return result
  }, [grouped, search])

  const filteredProviderOrder = useMemo(() => {
    return Object.keys(filteredGroups).sort((a, b) => {
      const pa = useCatalogStore.getState().getProviderByAlias(a)
      const pb = useCatalogStore.getState().getProviderByAlias(b)
      const na = pa?.name || a
      const nb = pb?.name || b
      return na.localeCompare(nb)
    })
  }, [filteredGroups])

  // Expand all providers that have search matches
  useEffect(() => {
    if (search.trim()) {
      setExpandedProviders(new Set(Object.keys(filteredGroups)))
    }
  }, [search, filteredGroups])

  // Toggle provider collapse
  const toggleProvider = useCallback((alias) => {
    setExpandedProviders((prev) => {
      const next = new Set(prev)
      if (next.has(alias)) next.delete(alias)
      else next.add(alias)
      return next
    })
  }, [])

  // Toggle model selection
  const toggleModel = useCallback((modelId) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(modelId)) next.delete(modelId)
      else next.add(modelId)
      return next
    })
  }, [])

  // Toggle all models in a provider
  const toggleProviderModels = useCallback((alias) => {
    const providerModels = filteredGroups[alias] || []
    setSelected((prev) => {
      const next = new Set(prev)
      const allSelected = providerModels.every((m) => next.has(m.id))
      for (const m of providerModels) {
        if (allSelected) next.delete(m.id)
        else next.add(m.id)
      }
      return next
    })
  }, [filteredGroups])

  // Handle add selected
  const handleAddSelected = useCallback(() => {
    const toAdd = [...selected].filter((id) => !existingModels.includes(id))
    if (toAdd.length > 0) onAdd(toAdd)
    onClose()
  }, [selected, existingModels, onAdd, onClose])

  // Keyboard handler
  useEffect(() => {
    if (!isOpen) return
    const handler = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  // Count selected that are new (not already in combo)
  const newSelectedCount = useMemo(
    () => [...selected].filter((id) => !existingModels.includes(id)).length,
    [selected, existingModels]
  )

  // Total model count
  const totalModels = useMemo(
    () => Object.values(grouped).reduce((sum, arr) => sum + arr.length, 0),
    [grouped]
  )

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      {/* Modal content */}
      <div className="relative z-10 w-full max-w-2xl mx-4 rounded-xl border border-zinc-700/50 bg-zinc-900 shadow-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700/50 shrink-0">
          <h3 className="text-lg font-semibold text-zinc-100">Select Models</h3>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>
        {/* Body */}
        <div className="px-6 py-4 flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Search bar */}
          <div className="relative mb-4 shrink-0">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              ref={searchRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search models or providers..."
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 pl-10 pr-10 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent hover:border-zinc-600"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Model list */}
          <div className="flex-1 overflow-y-auto min-h-0 -mx-2 px-2 space-y-1">
            {loading ? (
              <div className="flex items-center justify-center py-16 text-zinc-500">
                <Loader2 size={20} className="animate-spin mr-2" />
                <span className="text-sm">Loading available models...</span>
              </div>
            ) : filteredProviderOrder.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-zinc-500">
                <Search size={32} className="mb-3 opacity-40" />
                <p className="text-sm font-medium">No models found</p>
                <p className="text-xs mt-1 text-zinc-600">
                  {search ? 'Try a different search term' : 'No models available from active connections'}
                </p>
              </div>
            ) : (
              filteredProviderOrder.map((alias) => {
                const provider = useCatalogStore.getState().getProviderByAlias(alias)
                const providerName = provider?.name || alias
                const providerColor = provider?.color || '#71717a'
                const textIcon = provider?.textIcon || alias.slice(0, 2).toUpperCase()
                const providerModels = filteredGroups[alias]
                const isExpanded = expandedProviders.has(alias)
                const allSelected = providerModels.every((m) => selected.has(m.id))
                const someSelected = providerModels.some((m) => selected.has(m.id))

                return (
                  <div key={alias} className="rounded-lg border border-zinc-800/80 overflow-hidden">
                    {/* Provider header */}
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => toggleProvider(alias)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleProvider(alias) } }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 bg-zinc-800/30 hover:bg-zinc-800/60 transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        {isExpanded ? (
                          <ChevronDown size={14} className="text-zinc-500 shrink-0" />
                        ) : (
                          <ChevronRight size={14} className="text-zinc-500 shrink-0" />
                        )}
                        <span
                          className="inline-flex items-center justify-center w-6 h-6 rounded-md text-[10px] font-bold shrink-0"
                          style={{ backgroundColor: providerColor + '25', color: providerColor }}
                        >
                          {textIcon}
                        </span>
                        <span className="text-sm font-medium text-zinc-200 truncate">{providerName}</span>
                      </div>
                      <Badge variant="default" size="sm">
                        {providerModels.length}
                      </Badge>
                      {/* Select all for this provider */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          toggleProviderModels(alias)
                        }}
                        className={`ml-1 p-1 rounded transition-colors cursor-pointer ${
                          allSelected
                            ? 'text-primary-400'
                            : someSelected
                            ? 'text-primary-400/60'
                            : 'text-zinc-600 hover:text-zinc-400'
                        }`}
                        title={allSelected ? 'Deselect all' : 'Select all'}
                      >
                        <Check size={14} className={allSelected ? '' : 'opacity-40'} />
                      </button>
                    </div>

                    {/* Models grid */}
                    {isExpanded && (
                      <div className="px-3 py-2.5 grid grid-cols-1 gap-1">
                        {providerModels.map((m) => {
                          const modelId = m.id // e.g. "openai/gpt-4o"
                          const shortId = modelId.includes('/') ? modelId.split('/').slice(1).join('/') : modelId
                          const isExisting = existingModels.includes(modelId)
                          const isSelected = selected.has(modelId)

                          return (
                            <button
                              key={modelId}
                              onClick={() => toggleModel(modelId)}
                              disabled={isExisting}
                              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all cursor-pointer ${
                                isExisting
                                  ? 'bg-zinc-800/20 opacity-50 cursor-not-allowed'
                                  : isSelected
                                  ? 'bg-primary-600/15 border border-primary-500/30'
                                  : 'bg-zinc-800/30 border border-transparent hover:bg-zinc-800/60 hover:border-zinc-700/50'
                              }`}
                            >
                              {/* Checkbox */}
                              <div
                                className={`w-4 h-4 rounded shrink-0 flex items-center justify-center border transition-colors ${
                                  isSelected
                                    ? 'bg-primary-600 border-primary-500'
                                    : isExisting
                                    ? 'border-zinc-700 bg-zinc-800'
                                    : 'border-zinc-600 bg-zinc-800/50'
                                }`}
                              >
                                {(isSelected || isExisting) && <Check size={11} className="text-white" />}
                              </div>

                              {/* Model ID */}
                              <span className="flex-1 min-w-0 text-sm text-zinc-200 font-mono truncate" title={modelId}>
                                {shortId}
                              </span>

                              {/* Already in combo badge */}
                              {isExisting && (
                                <Badge variant="primary" size="sm">
                                  in combo
                                </Badge>
                              )}
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between pt-4 mt-2 border-t border-zinc-800 shrink-0">
            <div className="flex items-center gap-3 text-xs text-zinc-500">
              <span>{totalModels} models available</span>
              {newSelectedCount > 0 && (
                <span className="text-primary-400 font-medium">
                  {newSelectedCount} selected
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleAddSelected}
                disabled={newSelectedCount === 0}
                className="px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-primary-600 text-white hover:bg-primary-500"
              >
                Add {newSelectedCount > 0 ? `${newSelectedCount} ` : ''}Selected
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}
