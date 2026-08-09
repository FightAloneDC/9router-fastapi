import client from './client'

export const quotaApi = {
  // Get quota data for all provider connections
  getQuotaData: () => client.get('/quota'),

  // Get usage/quota for a single connection.
  // force=true bypasses the backend cache and always polls the
  // provider upstream (used by the manual refresh button).
  getUsage: (connectionId, force = false) =>
    client.get(`/usage/${connectionId}`, {
      params: force ? { force: true } : {},
    }),
}
