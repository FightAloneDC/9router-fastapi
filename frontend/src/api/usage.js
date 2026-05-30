import client from './client'

export const usageApi = {
  // Aggregated usage stats for a period
  getUsageStats: (period = '7d') =>
    client.get('/usage/stats', { params: { period } }),

  // Chart data points for a period
  getUsageChart: (period = '7d') =>
    client.get('/usage/chart', { params: { period } }),

  // Raw usage history with optional filters
  getUsageHistory: (filters = {}) =>
    client.get('/usage/history', { params: filters }),

  // Paginated request details
  getRequestDetails: (page = 1, pageSize = 20, filters = {}) =>
    client.get('/usage/request-details', {
      params: { page, pageSize, ...filters },
    }),

  // Get unique provider names from usage history
  getUsageProviders: () =>
    client.get('/usage/providers'),

  // Get full request detail by ID
  getRequestDetail: (id) =>
    client.get(`/usage/request-detail/${id}`),
}
