import axios from 'axios'

// API client for landing page - connects to saas-api
const API_URL = import.meta.env.VITE_SAAS_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Auth API - for signup from landing page
export const authApi = {
  register: (email: string, password: string, name: string, orgName: string) =>
    api.post('/auth/register', { 
      email, 
      password, 
      name,
      org_name: orgName
    }),
}

// Plans API - to display pricing
export const plansApi = {
  list: () => api.get('/plans'),
  get: (id: string) => api.get(`/plans/${id}`),
}

// Health check
export const healthApi = {
  check: () => api.get('/health'),
}
