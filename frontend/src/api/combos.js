import client from './client'

export const combosApi = {
  getCombos: () => client.get('/combos'),
  getCombo: (id) => client.get(`/combos/${id}`),
  createCombo: (data) => client.post('/combos', data),
  updateCombo: (id, data) => client.put(`/combos/${id}`, data),
  deleteCombo: (id) => client.delete(`/combos/${id}`),
}
