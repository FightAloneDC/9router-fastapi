import client from './client'

export const providersApi = {
  // Provider Connections
  getProviders: (params) => client.get('/providers', { params }),
  getProvidersClient: () => client.get('/providers/client'),
  getProvider: (id) => client.get(`/providers/${id}`),
  createProvider: (data) => client.post('/providers', data),
  updateProvider: (id, data) => client.patch(`/providers/${id}`, data),
  deleteProvider: (id) => client.delete(`/providers/${id}`),

  // Provider validation
  validateProvider: (data) => client.post('/providers/validate', data),

  // Provider testing
  testProvider: (id) => client.post(`/providers/${id}/test`),
  testBatch: (data) => client.post('/providers/test-batch', data),

  // Fetch models from provider API
  fetchProviderModels: (id) => client.get(`/providers/${id}/models`),
  clearProviderModels: (connId) => client.delete(`/providers/${connId}/models`),
  changeModelType: (connId, modelId, type) => client.patch(`/providers/${connId}/models/type`, { model_id: modelId, type }),

  // Suggested models
  getSuggestedModels: (params) => client.get('/providers/suggested-models', { params }),

  // Media providers (by service kind)
  getMediaProviders: (kind) => client.get(`/media-providers/${kind}`),
  getAllMediaProviders: () => client.get('/media-providers'),

  // Provider Nodes (custom OpenAI/Anthropic compatible)
  getProviderNodes: () => client.get('/provider-nodes'),
  createProviderNode: (data) => client.post('/provider-nodes', data),
  updateProviderNode: (id, data) => client.put(`/provider-nodes/${id}`, data),
  deleteProviderNode: (id) => client.delete(`/provider-nodes/${id}`),
  validateProviderNode: (data) => client.post('/provider-nodes/validate', data),

  // ── Model Management ──────────────────────────────────────────────────────
  // Model aliases
  getModelAliases: () => client.get('/models/alias'),
  setModelAlias: (data) => client.put('/models/alias', data),
  deleteModelAlias: (alias) => client.delete(`/models/alias?alias=${encodeURIComponent(alias)}`),

  // Custom models
  getCustomModels: () => client.get('/models/custom'),
  addCustomModel: (data) => client.post('/models/custom', data),
  deleteCustomModel: (params) => client.delete(`/models/custom`, { params }),

  // Disabled models
  getDisabledModels: (providerAlias) => client.get('/models/disabled', { params: { providerAlias } }),
  disableModels: (data) => client.post('/models/disabled', data),
  enableModel: (params) => client.delete('/models/disabled', { params }),
  enableAllModels: (providerAlias) => client.delete('/models/disabled', { params: { providerAlias } }),

  // Model availability / cooldown
  getModelAvailability: () => client.get('/models/availability'),
  clearModelCooldown: (data) => client.post('/models/availability', data),

  // Model test
  testModel: (data) => client.post('/models/test', data),

  // ── Settings ──────────────────────────────────────────────────────────────
  getSettings: () => client.get('/settings'),
  updateSettings: (data) => client.patch('/settings', data),

  // ── Proxy Pools ───────────────────────────────────────────────────────────
  getProxyPools: (params) => client.get('/proxy-pools', { params }),
  getProxyPool: (id) => client.get(`/proxy-pools/${id}`),
  createProxyPool: (data) => client.post('/proxy-pools', data),
  updateProxyPool: (id, data) => client.patch(`/proxy-pools/${id}`, data),
  deleteProxyPool: (id) => client.delete(`/proxy-pools/${id}`),
  testProxyPool: (id) => client.post(`/proxy-pools/${id}/test`),
}
