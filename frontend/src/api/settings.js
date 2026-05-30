import client from './client'

export const settingsApi = {
  get: () => client.get('/settings'),
  update: (data) => client.patch('/settings', data),
}
