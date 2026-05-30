import client from './client'

export const endpointsApi = {
  // API Keys
  getKeys: () => client.get('/api-keys'),
  createKey: (name) => client.post('/api-keys', { name: name || null }),
  deleteKey: (id) => client.delete(`/api-keys/${id}`),
  toggleKey: (id) => client.patch(`/api-keys/${id}`),

  // Settings
  getSettings: () => client.get('/settings'),
  updateSettings: (data) => client.patch('/settings', data),
}
