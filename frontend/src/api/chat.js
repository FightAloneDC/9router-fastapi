import client from './client'

export const chatApi = {
  getConversations: () => client.get('/chat/conversations'),
  getConversation: (id) => client.get(`/chat/conversations/${id}`),
  createConversation: (data) => client.post('/chat/conversations', data),
  updateConversation: (id, data) => client.patch(`/chat/conversations/${id}`, data),
  deleteConversation: (id) => client.delete(`/chat/conversations/${id}`),
  saveMessage: (conversationId, data) =>
    client.post(`/chat/conversations/${conversationId}/messages`, data),
}
