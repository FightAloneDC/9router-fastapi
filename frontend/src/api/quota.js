import client from './client'

export const quotaApi = {
  // Paginated quota tracker list (cached quotas embedded)
  getQuotaData: (params) => client.get('/quota', { params }),

  // Get usage/quota for a single connection.
  // force=true bypasses the backend cache and always polls the
  // provider upstream (used by the manual refresh button).
  getUsage: (connectionId, force = false) =>
    client.get(`/usage/${connectionId}`, {
      params: force ? { force: true } : {},
    }),

  bulkDisableDepleted: () =>
    client.post('/quota/bulk-disable-depleted'),

  bulkEnableInactive: () =>
    client.post('/quota/bulk-enable-inactive'),
}
