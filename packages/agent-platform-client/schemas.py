"""
Pydantic schemas for Agent Platform Client.

These match the schemas from the agent-api-specifications.md
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# AgentTask
# ============================================================================

class AgentTaskResponse(BaseModel):
    """Response schema for AgentTask."""
    id: str = Field(..., description="Unique task ID")
    tenant_id: str = Field(..., description="Tenant ID")
    agent_type: str = Field(..., description="Type of agent")
    action_type: str = Field(..., description="Type of action")
    status: str = Field(..., description="Current status")
    trust_level: str = Field(..., description="Trust level")
    reasoning_trace: str = Field(..., description="Full LLM reasoning trace")
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = Field(default=None)
    approval_request_id: Optional[str] = Field(default=None)
    related_entity_id: Optional[str] = Field(default=None)
    related_entity_type: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(..., description="When the task was created")
    updated_at: datetime = Field(..., description="When the task was last updated")
    completed_at: Optional[datetime] = Field(default=None)


# ============================================================================
# Shipment Tracking
# ============================================================================

class Address(BaseModel):
    """Address schema."""
    address: str
    city: str
    state: str
    zip: str
    country: str


class ShipmentBase(BaseModel):
    """Base schema for Shipment."""
    tracking_number: str
    carrier: str
    carrier_service: str
    origin: Address
    destination: Address
    estimated_delivery: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class ShipmentCreate(ShipmentBase):
    """Schema for creating a Shipment."""
    pass


class ShipmentResponse(ShipmentBase):
    """Response schema for Shipment."""
    id: str
    tenant_id: str
    status: str
    current_location: Optional[Dict[str, Any]] = None
    eta_drift_minutes: Optional[float] = None
    eta_drift_detected_at: Optional[datetime] = None
    carrier_account: Optional[str] = None
    billing_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    actual_delivery: Optional[datetime] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Route Optimization
# ============================================================================

class RouteStop(BaseModel):
    """Schema for a route stop."""
    location: Dict[str, Any]
    type: str  # pickup|delivery|both
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    shipment_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class RouteConstraint(BaseModel):
    """Schema for route constraints."""
    max_duration_minutes: Optional[int] = None
    max_distance_miles: Optional[float] = None
    vehicle_capacity_cubic_feet: Optional[float] = None
    vehicle_capacity_weight_lbs: Optional[float] = None


class RouteOptimizeRequest(BaseModel):
    """Request schema for route optimization."""
    warehouse_id: str
    date: str  # date in YYYY-MM-DD format
    stops: List[RouteStop]
    drivers: Optional[List[Dict[str, Any]]] = None
    vehicles: Optional[List[Dict[str, Any]]] = None
    constraints: RouteConstraint = Field(default_factory=RouteConstraint)


class RouteResponse(BaseModel):
    """Response schema for route optimization."""
    routes: List[Dict[str, Any]]
    unassigned_stops: List[Dict[str, Any]] = Field(default_factory=list)
    agent_task_id: str


# ============================================================================
# Inventory Management
# ============================================================================

class InventoryItemBase(BaseModel):
    """Base schema for InventoryItem."""
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    warehouse_id: str
    location: Optional[str] = None
    quantity_on_hand: int = 0
    reorder_point: int = 0
    reorder_quantity: int = 0
    unit_cost: float = 0.0
    unit_of_measure: Optional[str] = None
    expiry_date: Optional[str] = None
    batch_number: Optional[str] = None
    supplier_id: Optional[str] = None


class InventoryItemCreate(InventoryItemBase):
    """Schema for creating an InventoryItem."""
    pass


class InventoryItemResponse(InventoryItemBase):
    """Response schema for InventoryItem."""
    id: str
    tenant_id: str
    status: str
    quantity_reserved: int = 0
    quantity_available: int = 0
    low_stock_alert: bool = False
    created_at: datetime
    updated_at: datetime
    last_updated: Optional[datetime] = None


# ============================================================================
# Common Response
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response schema."""
    error: Dict[str, Any] = Field(..., description="Error details")


class ListResponse(BaseModel):
    """Generic list response schema."""
    items: List[Any] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0
