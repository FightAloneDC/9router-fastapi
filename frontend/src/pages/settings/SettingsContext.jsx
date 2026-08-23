import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'
import { settingsApi } from '../../api/settings'
import { useAutoSave } from './settingsUi'

const SettingsContext = createContext(null)

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [savingFields, setSavingFields] = useState({})
  const [savedFields, setSavedFields] = useState({})

  const saveField = useAutoSave(setSettings, setSavingFields, setSavedFields)

  const fetchSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await settingsApi.get()
      setSettings(res.data)
    } catch (err) {
      console.error('Failed to fetch settings:', err)
      const timedOut = err.code === 'ECONNABORTED'
      setError(
        timedOut
          ? 'Settings request timed out. Check that the backend is running.'
          : 'Failed to load settings',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const updateField = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
    saveField(key, value)
  }

  return (
    <SettingsContext.Provider
      value={{
        settings,
        loading,
        error,
        savingFields,
        savedFields,
        fetchSettings,
        updateField,
      }}
    >
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) {
    throw new Error('useSettings must be used within SettingsProvider')
  }
  return ctx
}
