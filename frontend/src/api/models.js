/**
 * Models API client — model availability and cooldown management.
 */
import api from './client'

export const modelsApi = {
  /** Get model availability status across all connections. */
  getAvailability: () => api.get('/models/availability'),

  /** Clear model cooldown for a specific provider/model. */
  clearCooldown: (provider, model) =>
    api.post('/models/availability', { action: 'clearCooldown', provider, model }),
}
