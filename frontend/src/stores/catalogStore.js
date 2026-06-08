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
