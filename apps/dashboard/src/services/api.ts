// API service for Lanework Dashboard

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

// Create axios instance with base configuration
const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for tenant ID and auth
api.interceptors.request.use((config: AxiosRequestConfig) => {
  const newConfig = { ...config };
  
  // Add tenant ID from localStorage
  const tenantId = localStorage.getItem('tenant_id');
  if (tenantId && newConfig.headers) {
    newConfig.headers['X-Tenant-ID'] = tenantId;
  }
  
  // Add auth token from localStorage
  const token = localStorage.getItem('token');
  if (token && newConfig.headers) {
    newConfig.headers['Authorization'] = `Bearer ${token}`;
  }
  
  return newConfig;
});

// Add response interceptor for error handling
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    if (error.response) {
      // Handle specific error statuses
      switch (error.response.status) {
        case 401:
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem('token');
          localStorage.removeItem('tenant_id');
          window.location.href = '/login';
          break;
        case 403:
          // Forbidden
          console.error('Access forbidden');
          break;
        case 404:
          // Not found
          console.error('Resource not found');
          break;
        case 500:
          // Server error
          console.error('Server error');
          break;
        default:
          console.error('API error:', error.response.status);
      }
    } else if (error.request) {
      // Network error
      console.error('Network error:', error.message);
    }
    
    return Promise.reject(error);
  }
);

// Generic API methods
export const apiService = {
  get: async <T>(url: string, config?: AxiosRequestConfig): Promise<T> => {
    const response = await api.get<T>(url, config);
    return response.data;
  },
  
  post: async <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await api.post<T>(url, data, config);
    return response.data;
  },
  
  put: async <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await api.put<T>(url, data, config);
    return response.data;
  },
  
  patch: async <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await api.patch<T>(url, data, config);
    return response.data;
  },
  
  delete: async <T>(url: string, config?: AxiosRequestConfig): Promise<T> => {
    const response = await api.delete<T>(url, config);
    return response.data;
  },
};

// Shipment API
export const shipmentApi = {
  list: async (params?: {
    status?: string;
    carrier?: string;
    tracking_number?: string;
    limit?: number;
    offset?: number;
  }) => {
    return apiService.get<PaginatedResponse<Shipment>>('/shipments', { params });
  },
  
  get: async (id: string) => {
    return apiService.get<Shipment>(`/shipments/${id}`);
  },
  
  create: async (data: Omit<Shipment, 'id' | 'tenant_id' | 'created_at' | 'updated_at'>) => {
    return apiService.post<Shipment>('/shipments', data);
  },
  
  update: async (id: string, data: Partial<Shipment>) => {
    return apiService.patch<Shipment>(`/shipments/${id}`, data);
  },
  
  delete: async (id: string) => {
    return apiService.delete<void>(`/shipments/${id}`);
  },
  
  refresh: async (id: string) => {
    return apiService.post<{ status: string; shipment_id: string; agent_task_id?: string }>(
      `/shipments/${id}/refresh`
    );
  },
  
  stats: async () => {
    return apiService.get<{ total_shipments: number; in_transit: number; delivered: number; delayed: number }>(
      '/shipments/stats'
    );
  },
};

// Inventory API
export const inventoryApi = {
  list: async (params?: {
    warehouse_id?: string;
    sku?: string;
    category?: string;
    low_stock?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    return apiService.get<PaginatedResponse<InventoryItem>>('/inventory/items', { params });
  },
  
  get: async (id: string) => {
    return apiService.get<InventoryItem>(`/inventory/items/${id}`);
  },
  
  create: async (data: Omit<InventoryItem, 'id' | 'tenant_id' | 'created_at' | 'updated_at'>) => {
    return apiService.post<InventoryItem>('/inventory/items', data);
  },
  
  update: async (id: string, data: Partial<InventoryItem>) => {
    return apiService.patch<InventoryItem>(`/inventory/items/${id}`, data);
  },
  
  delete: async (id: string) => {
    return apiService.delete<void>(`/inventory/items/${id}`);
  },
  
  adjust: async (id: string, data: { adjustment_type: string; quantity: number; reference?: string; notes?: string }) => {
    return apiService.post<InventoryItem>(`/inventory/items/${id}/adjust`, data);
  },
  
  reserve: async (id: string, data: { reservation_id: string; order_id?: string; quantity: number }) => {
    return apiService.post<InventoryItem>(`/inventory/items/${id}/reserve`, data);
  },
  
  release: async (id: string, data: { reservation_id: string; quantity?: number }) => {
    return apiService.post<InventoryItem>(`/inventory/items/${id}/release`, data);
  },
  
  stats: async () => {
    return apiService.get<{
      total_items: number;
      total_quantity: number;
      total_value: number;
      low_stock_items: number;
      out_of_stock_items: number;
    }>('/inventory/stats');
  },
  
  lowStock: async () => {
    return apiService.get<LowStockAlert[]>('/inventory/low-stock');
  },
};

// Route API
export const routeApi = {
  list: async (params?: {
    status?: RouteStatus;
    driver_id?: string;
    vehicle_id?: string;
    date?: string;
    warehouse_id?: string;
    limit?: number;
    offset?: number;
  }) => {
    return apiService.get<PaginatedResponse<Route>>('/routes', { params });
  },
  
  get: async (id: string) => {
    return apiService.get<Route>(`/routes/${id}`);
  },
  
  create: async (data: Omit<Route, 'id' | 'tenant_id' | 'created_at' | 'updated_at' | 'stops'> & { stops: RouteStop[] }) => {
    return apiService.post<Route>('/routes', data);
  },
  
  update: async (id: string, data: Partial<Route>) => {
    return apiService.patch<Route>(`/routes/${id}`, data);
  },
  
  delete: async (id: string) => {
    return apiService.delete<void>(`/routes/${id}`);
  },
  
  optimize: async (data: {
    warehouse_id: string;
    date: string;
    stops: RouteStop[];
    drivers?: DriverInfo[];
    vehicles?: VehicleInfo[];
    constraints?: RouteConstraints;
  }) => {
    return apiService.post<RouteOptimizationResponse>('/routes/optimize', data);
  },
  
  reoptimize: async (id: string, data: { trigger: ReoptimizationTrigger; new_stop?: RouteStop; removed_stop_ids?: string[] }) => {
    return apiService.post<RouteReoptimizationResponse>(`/routes/${id}/reoptimize`, data);
  },
  
  assign: async (id: string, data: { driver_id: string; vehicle_id: string; start_time?: string }) => {
    return apiService.post<RouteAssignmentResponse>(`/routes/${id}/assign`, data);
  },
  
  start: async (id: string) => {
    return apiService.post<Route>(`/routes/${id}/start`);
  },
  
  complete: async (id: string) => {
    return apiService.post<Route>(`/routes/${id}/complete`);
  },
  
  stats: async () => {
    return apiService.get<RouteStats>('/routes/stats');
  },
};

// Agent Task API
export const agentTaskApi = {
  list: async (params?: {
    agent_type?: AgentType;
    status?: AgentTaskStatus;
    limit?: number;
    offset?: number;
  }) => {
    return apiService.get<PaginatedResponse<AgentTask>>('/agent-tasks', { params });
  },
  
  get: async (id: string) => {
    return apiService.get<AgentTask>(`/agent-tasks/${id}`);
  },
  
  approve: async (id: string) => {
    return apiService.post<AgentTask>(`/agent-tasks/${id}/approve`);
  },
  
  reject: async (id: string, reason?: string) => {
    return apiService.post<AgentTask>(`/agent-tasks/${id}/reject`, { reason });
  },
};

// Approval API
export const approvalApi = {
  list: async (params?: {
    status?: 'pending' | 'approved' | 'rejected' | 'expired';
    limit?: number;
    offset?: number;
  }) => {
    return apiService.get<PaginatedResponse<ApprovalRequest>>('/approvals', { params });
  },
  
  get: async (id: string) => {
    return apiService.get<ApprovalRequest>(`/approvals/${id}`);
  },
  
  approve: async (id: string) => {
    return apiService.post<ApprovalRequest>(`/approvals/${id}/approve`);
  },
  
  reject: async (id: string, reason?: string) => {
    return apiService.post<ApprovalRequest>(`/approvals/${id}/reject`, { reason });
  },
};

// Chat API
export const chatApi = {
  sendMessage: async (data: { message: string; conversation_id?: string }) => {
    return apiService.post<ChatResponse>('/chat', data);
  },
  
  listConversations: async (params?: { participant_id?: string; limit?: number; offset?: number }) => {
    return apiService.get<ConversationListResponse>('/conversations', { params });
  },
  
  getConversation: async (id: string) => {
    return apiService.get<Conversation>(`/conversations/${id}`);
  },
  
  deleteConversation: async (id: string) => {
    return apiService.delete<void>(`/conversations/${id}`);
  },
  
  getSuggestedPrompts: async () => {
    return apiService.get<string[]>('/chat/suggested-prompts');
  },
};

// Health check
export const healthApi = {
  check: async () => {
    return apiService.get<{ status: string; service: string; version: string }>('/health');
  },
  
  checkAgent: async (agent: AgentType) => {
    return apiService.get<{ status: string; agent: string; version: string }>(`/${agent}/health`);
  },
};

// Export all APIs
export {
  api,
  apiService,
};
