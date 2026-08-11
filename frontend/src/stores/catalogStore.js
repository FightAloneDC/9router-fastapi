import { create } from 'zustand'
import client from '../api/client'

const useCatalogStore = create((set, get) => ({
  providers: {},
  categories: {},
  mediaKinds: [],
  compatiblePrefixes: {},
  authMethods: {},
  loaded: false,
  loading: false,
  _ensuring: {},

  fetchCatalog: async () => {
    if (get().loaded || get().loading) return
    set({ loading: true })
    try {
      const res = await client.get('/providers/catalog')
      const data = res.data
      set({
        providers: data.providers || {},
        categories: data.categories || {},
        mediaKinds: data.mediaKinds || [],
        compatiblePrefixes: data.compatiblePrefixes || {},
        authMethods: data.authMethods || {},
        loaded: true,
        loading: false,
      })
    } catch (err) {
      console.error('[catalog] Failed to fetch provider catalog:', err)
      set({ loading: false })
    }
  },

  /**
   * Load a single provider's catalog entry (for detail pages).
   * No-ops if full catalog is already loaded or the provider is present.
   */
  ensureProvider: async (idOrAlias) => {
    if (!idOrAlias) return null
    const state = get()
    if (state.loaded) {
      return state.getProviderByAlias(idOrAlias) || state.providers[idOrAlias] || null
    }
    const existing =
      state.providers[idOrAlias] || state.getProviderByAlias(idOrAlias)
    if (existing) return existing

    if (state._ensuring[idOrAlias]) {
      return state._ensuring[idOrAlias]
    }

    const pending = (async () => {
      try {
        const res = await client.get(`/providers/catalog/${encodeURIComponent(idOrAlias)}`)
        const data = res.data || {}
        const provider = data.provider
        if (!provider?.id) return null
        set((s) => ({
          providers: { ...s.providers, [provider.id]: provider },
          compatiblePrefixes: data.compatiblePrefixes || s.compatiblePrefixes,
          authMethods: data.authMethods || s.authMethods,
        }))
        return provider
      } catch (err) {
        console.error('[catalog] Failed to fetch provider entry:', err)
        return null
      } finally {
        set((s) => {
          const next = { ...s._ensuring }
          delete next[idOrAlias]
          return { _ensuring: next }
        })
      }
    })()

    set((s) => ({
      _ensuring: { ...s._ensuring, [idOrAlias]: pending },
    }))
    return pending
  },

  // ── Accessors ────────────────────────────────────────────────────────

  getProvider: (id) => get().providers[id],

  getProviderByAlias: (alias) => {
    for (const p of Object.values(get().providers)) {
      if (p.alias === alias || p.id === alias) return p
    }
    return null
  },

  resolveProviderId: (aliasOrId) => {
    const p = get().getProviderByAlias(aliasOrId)
    return p?.id || aliasOrId
  },

  getProvidersByKind: (kind) => {
    return Object.values(get().providers)
      .filter((p) => {
        const kinds = p.serviceKinds ?? ['llm']
        if (!kinds.includes(kind)) return false
        if (p.hidden) return false
        return true
      })
      .sort((a, b) => (a.mediaPriority ?? 100) - (b.mediaPriority ?? 100))
  },

  getKindConfig: (kindId) => {
    return get().mediaKinds.find((k) => k.id === kindId)
  },

  // ── Derived maps ─────────────────────────────────────────────────────

  getAliasToId: () => {
    const map = {}
    for (const p of Object.values(get().providers)) {
      map[p.alias] = p.id
    }
    return map
  },

  getIdToAlias: () => {
    const map = {}
    for (const p of Object.values(get().providers)) {
      map[p.id] = p.alias
    }
    return map
  },

  getProviderAlias: (id) => {
    const p = get().providers[id]
    return p?.alias || id
  },

  // ── Category-derived dicts (backward compat with constants/providers.js) ──

  _getCategoryDict: (category) => {
    const ids = get().categories[category] || []
    const result = {}
    for (const id of ids) {
      if (get().providers[id]) result[id] = get().providers[id]
    }
    return result
  },

  getOauthProviders: () => get()._getCategoryDict('oauth'),
  getFreeProviders: () => get()._getCategoryDict('free'),
  getFreeTierProviders: () => get()._getCategoryDict('freeTier'),
  getApiKeyProviders: () => get()._getCategoryDict('apiKey'),
  getWebCookieProviders: () => get()._getCategoryDict('webCookie'),

  // ── Category checks ───────────────────────────────────────────────────

  isOpenAICompatibleProvider: (id) => {
    const prefix = get().compatiblePrefixes.openai || 'openai-compatible-'
    return typeof id === 'string' && id.startsWith(prefix)
  },

  isAnthropicCompatibleProvider: (id) => {
    const prefix = get().compatiblePrefixes.anthropic || 'anthropic-compatible-'
    return typeof id === 'string' && id.startsWith(prefix)
  },

  isOpenAICompatibleNode: (node) => {
    return node?.type === 'openai-compatible'
  },

  isAnthropicCompatibleNode: (node) => {
    return node?.type === 'anthropic-compatible'
  },

  // ── OAuth provider checks ─────────────────────────────────────────────

  isOAuthProvider: (id) => {
    const p = get().providers[id]
    return p?.authType === 'oauth'
  },

  isFreeProvider: (id) => {
    const p = get().providers[id]
    return p?.authType === 'free' || p?.noAuth === true
  },

  isCookieProvider: (id) => {
    const p = get().providers[id]
    return p?.authType === 'cookie'
  },
}))

export default useCatalogStore
