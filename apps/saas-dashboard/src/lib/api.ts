import axios from 'axios'

// Create API client
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor to include auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Add response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired - clear and redirect to login
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  register: (email: string, password: string, name: string) =>
    api.post('/auth/register', { email, password, name }),
  me: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
}

// Organization API
export const orgApi = {
  list: () => api.get('/organizations'),
  create: (data: any) => api.post('/organizations', data),
  get: (id: string) => api.get(`/organizations/${id}`),
  update: (id: string, data: any) => api.patch(`/organizations/${id}`, data),
  delete: (id: string) => api.delete(`/organizations/${id}`),
}

// Plan API
export const planApi = {
  list: () => api.get('/plans'),
  create: (data: any) => api.post('/plans', data),
  get: (id: string) => api.get(`/plans/${id}`),
  update: (id: string, data: any) => api.patch(`/plans/${id}`, data),
  delete: (id: string) => api.delete(`/plans/${id}`),
}

// User API
export const userApi = {
  list: () => api.get('/users'),
  create: (data: any) => api.post('/users', data),
  get: (id: string) => api.get(`/users/${id}`),
  update: (id: string, data: any) => api.patch(`/users/${id}`, data),
  delete: (id: string) => api.delete(`/users/${id}`),
}

// Health API
export const healthApi = {
  check: () => api.get('/health'),
  db: () => api.get('/health/db'),
}
