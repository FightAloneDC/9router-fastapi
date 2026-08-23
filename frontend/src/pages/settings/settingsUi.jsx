import { useState, useCallback, useRef } from 'react'
import { Check } from 'lucide-react'
import Card, { CardContent, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import { settingsApi } from '../../api/settings'

export function useTheme() {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === 'undefined') return 'system'
    return localStorage.getItem('9router-theme') || 'system'
  })

  const setTheme = (t) => {
    setThemeState(t)
    localStorage.setItem('9router-theme', t)
    const dark =
      t === 'dark' ||
      (t === 'system' &&
        window.matchMedia('(prefers-color-scheme: dark)').matches)
    document.documentElement.classList.toggle('dark', dark)
  }

  return { theme, setTheme }
}

export function Section({ icon: Icon, title, description, badge, children }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-zinc-800">
            <Icon size={18} className="text-zinc-400" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-zinc-100">{title}</h3>
              {badge}
            </div>
            {description && (
              <p className="text-sm text-zinc-500 mt-0.5">{description}</p>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-5">{children}</div>
      </CardContent>
    </Card>
  )
}

export function SettingRow({ label, description, saving, saved, children }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-zinc-200">{label}</p>
        {description && (
          <p className="text-xs text-zinc-500 mt-0.5">{description}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {saving && (
          <span className="text-xs text-zinc-500 animate-pulse">Saving...</span>
        )}
        {saved && (
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            <Check size={12} /> Saved
          </span>
        )}
        {children}
      </div>
    </div>
  )
}

export function SelectInput({ value, onChange, options, className = '' }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent hover:border-zinc-600 transition-colors ${className}`}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}

export function DictEditor({
  value,
  onChange,
  keyLabel = 'Key',
  valueLabel = 'Value',
}) {
  const entries = Object.entries(value || {})
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')

  const addEntry = () => {
    if (!newKey.trim()) return
    onChange({ ...value, [newKey.trim()]: newValue })
    setNewKey('')
    setNewValue('')
  }

  const removeEntry = (key) => {
    const next = { ...value }
    delete next[key]
    onChange(next)
  }

  const updateEntry = (key, val) => {
    onChange({ ...value, [key]: val })
  }

  return (
    <div className="space-y-2 w-full max-w-md">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="text-xs text-zinc-400 font-mono min-w-[80px] truncate">
            {k}
          </span>
          <Input
            value={typeof v === 'string' ? v : JSON.stringify(v)}
            onChange={(e) => updateEntry(k, e.target.value)}
            className="flex-1 text-xs"
          />
          <button
            onClick={() => removeEntry(k)}
            className="text-zinc-500 hover:text-red-400 text-xs px-1"
          >
            ×
          </button>
        </div>
      ))}
      <div className="flex items-center gap-2">
        <Input
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          placeholder={keyLabel}
          className="flex-1 text-xs"
        />
        <Input
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          placeholder={valueLabel}
          className="flex-1 text-xs"
        />
        <button
          onClick={addEntry}
          className="text-xs text-primary-400 hover:text-primary-300 px-2 py-1 rounded bg-zinc-800"
        >
          +
        </button>
      </div>
    </div>
  )
}

export function useAutoSave(
  setSettings,
  setSavingFields,
  setSavedFields,
) {
  const debounceRef = useRef({})

  const saveField = useCallback(async (key, value) => {
    if (debounceRef.current[key]) {
      clearTimeout(debounceRef.current[key])
    }

    const isText = typeof value === 'string'
    const delay = isText ? 500 : 0

    debounceRef.current[key] = setTimeout(async () => {
      setSavingFields((prev) => ({ ...prev, [key]: true }))
      setSavedFields((prev) => ({ ...prev, [key]: false }))
      try {
        const res = await settingsApi.update({ [key]: value })
        if (res?.data) {
          setSettings(res.data)
        }
        setSavedFields((prev) => ({ ...prev, [key]: true }))
        setTimeout(
          () => setSavedFields((prev) => ({ ...prev, [key]: false })),
          2000,
        )
      } catch (err) {
        console.error(`Failed to save ${key}:`, err)
      } finally {
        setSavingFields((prev) => ({ ...prev, [key]: false }))
      }
    }, delay)
  }, [setSettings, setSavingFields, setSavedFields])

  return saveField
}

export function SettingsLoading() {
  return (
    <div className="space-y-6">
      {[...Array(2)].map((_, i) => (
        <Card key={i}>
          <CardContent>
            <div className="animate-pulse space-y-4">
              <div className="h-5 w-40 rounded bg-zinc-800" />
              <div className="h-10 w-full rounded bg-zinc-800" />
              <div className="h-10 w-full rounded bg-zinc-800" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
