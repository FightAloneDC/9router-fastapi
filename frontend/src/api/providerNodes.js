import client from './client'

/**
 * Provider Nodes API - custom OpenAI/Anthropic-compatible provider endpoints.
 *
 * Backend routes: /provider-nodes/*
 * See backend/app/routers/providers.py (lines 1010-1401)
 */
export const providerNodesApi = {
  /** List all custom provider nodes */
  list: () => client.get('/provider-nodes'),

  /** Create a new provider node */
  create: (data) => client.post('/provider-nodes', data),

  /** Update an existing provider node (full replace) */
  update: (id, data) => client.put(`/provider-nodes/${id}`, data),

  /** Delete a provider node and its associated connections */
  delete: (id) => client.delete(`/provider-nodes/${id}`),

  /**
   * Validate an API key against a compatible provider.
   *
   * @param {{ base_url: string, api_key: string, type?: string, model_id?: string }} data
   *   - type: 'openai-compatible' | 'anthropic-compatible' | 'custom-embedding'
   *   - model_id: optional, for fallback chat/completions validation
   * @returns {{ valid: boolean, method?: string, dimensions?: number, error?: string }}
   */
  validate: (data) => client.post('/provider-nodes/validate', data),
}
