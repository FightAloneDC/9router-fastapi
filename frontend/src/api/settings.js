import client from './client'

export const settingsApi = {
  get: () => client.get('/settings'),
  update: (data) => client.patch('/settings', data),
  exportDatabase: () => client.get('/settings/database'),
  importDatabase: (data) => client.post('/settings/database', data),
  exportConnections: (params) =>
    client.get('/settings/database/connections', { params }),
  importConnections: (data, params) =>
    client.post('/settings/database/connections', data, { params }),
}
