import client from './client'

// Get all CLI tool configs
export const getCliTools = () => client.get('/cli-tools')

// Get a single CLI tool config by id
export const getCliTool = (id) => client.get(`/cli-tools/${id}`)

// Update a CLI tool config (partial merge)
export const updateCliTool = (id, data) => client.patch(`/cli-tools/${id}`, data)
