import client from './client'

export const quotaApi = {
  // Paginated quota tracker list (cached quotas embedded)
  getQuotaData: (params) => client.get('/quota', { params }),

  // Get usage/quota for a single connection.
  // force=true bypasses the backend cache and always polls the
  // provider upstream (used by the manual refresh button).
  // detail='models' loads the full per-model table (alims-intl);
  // that response is not written to quota_cache.
  getUsage: (connectionId, force = false, detail = null) =>
    client.get(`/usage/${connectionId}`, {
      params: {
        ...(force ? { force: true } : {}),
        ...(detail ? { detail } : {}),
      },
    }),

  bulkDisableDepleted: () =>
    client.post('/quota/bulk-disable-depleted'),

  bulkEnableInactive: () =>
    client.post('/quota/bulk-enable-inactive'),
}
