import client from './client'

export const proxyPoolsApi = {
  getAll: () => client.get('/proxy-pools'),
  create: (data) => client.post('/proxy-pools', data),
  update: (id, data) => client.patch(`/proxy-pools/${id}`, data),
  delete: (id) => client.delete(`/proxy-pools/${id}`),
  test: (id) => client.post(`/proxy-pools/${id}/test`),
  applyUsage: (id) => client.post(`/proxy-pools/${id}/apply-usage`),
}
