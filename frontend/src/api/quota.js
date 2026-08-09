import client from './client'

export const quotaApi = {
  // Get quota data for all provider connections
  getQuotaData: () => client.get('/quota'),

  // Get real-time usage/quota for a single connection
  getUsage: (connectionId) =>
    client.get(`/usage/${connectionId}`),
}
