import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search, X } from 'lucide-react'

/**
 * Filterable single-select (Select2-like, no extra library).
 */
export default function SearchableSelect({
  value,
  onChange,
  options = [],
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  allowCustom = false,
  disabled = false,
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [hi, setHi] = useState(0)
  const rootRef = useRef(null)
  const inputRef = useRef(null)
  const listRef = useRef(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return options
    return options.filter((o) => {
      const label = String(o.label || o.value || '')
      return label.toLowerCase().includes(q)
    })
  }, [options, query])

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => {
      if (!rootRef.current?.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  useEffect(() => {
    if (open) {
      setQuery('')
      setHi(0)
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  useEffect(() => {
    if (!open || !listRef.current) return
    const el = listRef.current.querySelector('[data-hi="1"]')
    el?.scrollIntoView({ block: 'nearest' })
  }, [hi, open, filtered])

  const pick = (next) => {
    onChange(next)
    setOpen(false)
  }

  const onKey = (e) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === 'ArrowDown') {
        e.preventDefault()
        setOpen(true)
      }
      return
    }
    if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHi((i) => Math.min(i + 1, Math.max(0, filtered.length - 1)))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHi((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      const hit = filtered[hi]
      if (hit) {
        pick(hit.value)
        return
      }
      if (allowCustom && query.trim()) {
        pick(query.trim())
      }
    }
  }

  const shown = value || placeholder

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        onKeyDown={onKey}
        className="flex w-full items-center gap-2 rounded-lg border
          border-zinc-700 bg-zinc-800 px-3 py-2 text-left text-sm
          text-zinc-200 disabled:opacity-50"
      >
        <span className={`min-w-0 flex-1 truncate ${
          value ? 'text-zinc-200' : 'text-zinc-500'
        }`}>
          {shown}
        </span>
        {value ? (
          <span
            role="button"
            tabIndex={-1}
            onClick={(e) => {
              e.stopPropagation()
              onChange('')
            }}
            className="shrink-0 text-zinc-500 hover:text-zinc-300"
          >
            <X size={14} />
          </span>
        ) : null}
        <ChevronDown size={14} className="shrink-0 text-zinc-500" />
      </button>
      {open && (
        <div
          className="absolute z-30 mt-1 w-full overflow-hidden
            rounded-lg border border-zinc-700 bg-zinc-900 shadow-lg"
        >
          <div className="relative border-b border-zinc-800">
            <Search
              size={14}
              className="pointer-events-none absolute left-2.5
                top-1/2 -translate-y-1/2 text-zinc-500"
            />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setHi(0)
              }}
              onKeyDown={onKey}
              placeholder={searchPlaceholder}
              className="w-full bg-transparent py-2 pl-8 pr-3 text-sm
                text-zinc-200 placeholder:text-zinc-600
                focus:outline-none"
            />
          </div>
          <ul
            ref={listRef}
            className="max-h-56 overflow-y-auto py-1"
          >
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-xs text-zinc-500">
                {allowCustom && query.trim()
                  ? `Use “${query.trim()}”`
                  : 'No matches'}
              </li>
            )}
            {filtered.map((o, i) => (
              <li key={o.value}>
                <button
                  type="button"
                  data-hi={i === hi ? '1' : '0'}
                  onMouseEnter={() => setHi(i)}
                  onClick={() => pick(o.value)}
                  className={`block w-full truncate px-3 py-1.5
                    text-left text-sm ${
                    i === hi
                      ? 'bg-zinc-800 text-zinc-100'
                      : 'text-zinc-300'
                  } ${o.value === value ? 'text-primary-400' : ''}`}
                >
                  {o.label || o.value}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
