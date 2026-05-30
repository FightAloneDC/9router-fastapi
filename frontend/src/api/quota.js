import client from './client'

export const quotaApi = {
  // Get quota data for all provider connections
  getQuotaData: () => client.get('/quota'),
}
