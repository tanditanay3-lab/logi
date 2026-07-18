// Types for Lanework Dashboard

// Agent types
export type AgentType = 
  | 'shipment-tracking'
  | 'inventory'
  | 'route-optimization'
  | 'warehouse-ops'
  | 'fleet-management'
  | 'customer-communication'
  | 'demand-forecasting'
  | 'freight-procurement'
  | 'voice';

// Trust levels
export type TrustLevel = 'propose_only' | 'auto_execute_low_risk' | 'fully_autonomous';

// Task status
export type AgentTaskStatus = 
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'auto_executed'
  | 'failed'
  | 'completed';

// Shipment status
export type ShipmentStatus = 
  | 'pending'
  | 'in_transit'
  | 'delivered'
  | 'cancelled'
  | 'delayed';

// Route status
export type RouteStatus = 
  | 'pending'
  | 'assigned'
  | 'in_progress'
  | 'completed'
  | 'cancelled';

// Inventory status
export type InventoryStatus = 'active' | 'inactive' | 'quarantined';

// Common response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// Agent Task
export interface AgentTask {
  id: string;
  tenant_id: string;
  agent_type: AgentType;
  action_type: string;
  status: AgentTaskStatus;
  trust_level: TrustLevel;
  reasoning_trace: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown> | null;
  approval_request_id: string | null;
  related_entity_id: string | null;
  related_entity_type: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

// Shipment
export interface Shipment {
  id: string;
  tenant_id: string;
  tracking_number: string;
  carrier: string;
  carrier_service: string | null;
  status: ShipmentStatus;
  origin: Location;
  destination: Location;
  estimated_delivery: string | null;
  actual_delivery: string | null;
  current_location: Location | null;
  eta_drift_minutes: number | null;
  eta_drift_detected_at: string | null;
  metadata: Record<string, unknown>;
  carrier_account: string | null;
  billing_reference: string | null;
  notes: string | null;
  events: ShipmentEvent[];
  created_at: string;
  updated_at: string;
}

// Location
export interface Location {
  address?: string;
  city?: string;
  state?: string;
  zip?: string;
  country?: string;
  lat?: number;
  lng?: number;
}

// Shipment Event
export interface ShipmentEvent {
  id: string;
  timestamp: string;
  event_type: string;
  description: string;
  location: Location | null;
  carrier_timestamp: string | null;
}

// Inventory Item
export interface InventoryItem {
  id: string;
  tenant_id: string;
  sku: string;
  name: string;
  description: string | null;
  category: string | null;
  warehouse_id: string | null;
  location: Location | null;
  quantity_on_hand: number;
  quantity_reserved: number;
  quantity_available: number;
  reorder_point: number;
  reorder_quantity: number;
  unit_cost: number;
  unit_of_measure: string;
  low_stock_alert: boolean;
  expiry_date: string | null;
  batch_number: string | null;
  status: InventoryStatus;
  metadata: Record<string, unknown>;
  supplier_id: string | null;
  last_updated: string | null;
  created_at: string;
  updated_at: string;
}

// Route
export interface Route {
  id: string;
  tenant_id: string;
  name: string;
  warehouse_id: string;
  date: string;
  status: RouteStatus;
  driver_id: string | null;
  vehicle_id: string | null;
  total_distance_miles: number;
  total_duration_minutes: number;
  total_stops: number;
  optimization_score: number;
  constraints: RouteConstraints;
  metrics: RouteMetrics;
  assigned_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  stops: RouteStop[];
  reoptimization_history: unknown[];
}

// Route Constraints
export interface RouteConstraints {
  max_duration_minutes?: number;
  max_distance_miles?: number;
  vehicle_capacity_cubic_feet?: number;
  vehicle_capacity_weight_lbs?: number;
  driver_hours_available?: number;
}

// Route Metrics
export interface RouteMetrics {
  fuel_cost: number;
  toll_cost: number;
  driver_pay: number;
  total_cost: number;
}

// Route Stop
export interface RouteStop {
  id: string;
  sequence: number;
  location: Location;
  stop_type: 'pickup' | 'delivery' | 'both';
  time_window_start: string | null;
  time_window_end: string | null;
  estimated_arrival: string | null;
  actual_arrival: string | null;
  estimated_departure: string | null;
  actual_departure: string | null;
  shipment_ids: string[];
  required_skills: string[];
  weight_lbs: number;
  cubic_feet: number;
  status: 'pending' | 'in_progress' | 'completed' | 'skipped';
  notes: string | null;
}

// Conversation
export interface Conversation {
  id: string;
  tenant_id: string;
  channel: 'chat' | 'voice';
  participant_type: string;
  participant_id: string | null;
  messages: ConversationMessage[];
  related_agent_task_ids: string[];
  voice_call_id: string | null;
  created_at: string;
  updated_at: string;
}

// Conversation Message
export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

// Voice Call
export interface VoiceCall {
  id: string;
  tenant_id: string;
  direction: 'inbound' | 'outbound';
  caller_type: 'driver' | 'customer' | 'dispatcher' | 'unknown';
  phone_number: string;
  transcript: string | null;
  structured_intent: Record<string, unknown> | null;
  duration_seconds: number | null;
  escalated_to_human: boolean;
  recording_url: string | null;
  related_agent_task_ids: string[];
  timestamp: string;
  ended_at: string | null;
}

// Stats
export interface DashboardStats {
  agent_tasks: {
    total: number;
    pending_approval: number;
    auto_executed: number;
    completed: number;
    failed: number;
  };
  shipments: {
    total: number;
    in_transit: number;
    delivered: number;
    delayed: number;
  };
  inventory: {
    total_items: number;
    low_stock: number;
    out_of_stock: number;
  };
  routes: {
    total: number;
    pending: number;
    in_progress: number;
    completed: number;
  };
}

// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

// Notification
export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  created_at: string;
  read: boolean;
}
