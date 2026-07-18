"""
Schemas for the Route Optimization Agent.
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.shared_types.schemas import AgentType, TrustLevel


class RouteStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RouteStopStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class RouteStopType(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    BOTH = "both"


class ReoptimizationTrigger(str, Enum):
    MANUAL = "manual"
    DELAY = "delay"
    DRIVER_ISSUE = "driver_issue"
    TRAFFIC = "traffic"
    WEATHER = "weather"
    NEW_STOP = "new_stop"


class Location(BaseModel):
    """Location model with coordinates."""
    address: str = Field(..., description="Street address")
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    zip: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class RouteConstraints(BaseModel):
    """Route constraints."""
    max_duration_minutes: Optional[int] = Field(default=None, description="Maximum route duration")
    max_distance_miles: Optional[float] = Field(default=None, description="Maximum route distance")
    vehicle_capacity_cubic_feet: Optional[float] = Field(default=None, description="Vehicle capacity in cubic feet")
    vehicle_capacity_weight_lbs: Optional[float] = Field(default=None, description="Vehicle capacity in pounds")
    driver_hours_available: Optional[float] = Field(default=None, description="Driver hours available")


class RouteMetrics(BaseModel):
    """Route metrics."""
    fuel_cost: float = Field(default=0.0, description="Fuel cost")
    toll_cost: float = Field(default=0.0, description="Toll cost")
    driver_pay: float = Field(default=0.0, description="Driver pay")
    total_cost: float = Field(default=0.0, description="Total cost")


class RouteStopBase(BaseModel):
    """Base route stop model."""
    location: Location = Field(..., description="Stop location")
    stop_type: RouteStopType = Field(default=RouteStopType.DELIVERY, description="Type of stop")
    time_window_start: Optional[time] = Field(default=None, description="Start of time window")
    time_window_end: Optional[time] = Field(default=None, description="End of time window")
    shipment_ids: List[str] = Field(default_factory=list, description="Shipment IDs for this stop")
    required_skills: List[str] = Field(default_factory=list, description="Required skills for this stop")
    weight_lbs: float = Field(default=0.0, description="Total weight for this stop")
    cubic_feet: float = Field(default=0.0, description="Total volume for this stop")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class RouteStopCreate(RouteStopBase):
    """Create route stop request."""
    pass


class RouteStop(RouteStopBase):
    """Full route stop model."""
    id: str
    sequence: int = Field(..., description="Sequence number in the route")
    estimated_arrival: Optional[time] = Field(default=None, description="Estimated arrival time")
    actual_arrival: Optional[time] = Field(default=None, description="Actual arrival time")
    estimated_departure: Optional[time] = Field(default=None, description="Estimated departure time")
    actual_departure: Optional[time] = Field(default=None, description="Actual departure time")
    status: RouteStopStatus = Field(default=RouteStopStatus.PENDING, description="Stop status")


class RouteStopUpdate(BaseModel):
    """Update route stop request."""
    location: Optional[Location] = None
    stop_type: Optional[RouteStopType] = None
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None
    shipment_ids: Optional[List[str]] = None
    required_skills: Optional[List[str]] = None
    weight_lbs: Optional[float] = None
    cubic_feet: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[RouteStopStatus] = None


class RouteBase(BaseModel):
    """Base route model."""
    name: str = Field(..., description="Route name")
    warehouse_id: str = Field(..., description="Origin warehouse ID")
    date: date = Field(..., description="Route date")
    stops: List[RouteStopCreate] = Field(default_factory=list, description="Route stops")
    constraints: RouteConstraints = Field(default_factory=RouteConstraints)


class RouteCreate(RouteBase):
    """Create route request."""
    pass


class Route(RouteBase):
    """Full route model."""
    id: str
    tenant_id: str
    status: RouteStatus = Field(default=RouteStatus.PENDING, description="Route status")
    driver_id: Optional[str] = Field(default=None, description="Assigned driver ID")
    vehicle_id: Optional[str] = Field(default=None, description="Assigned vehicle ID")
    total_distance_miles: float = Field(default=0.0, description="Total distance in miles")
    total_duration_minutes: int = Field(default=0, description="Total duration in minutes")
    total_stops: int = Field(default=0, description="Total number of stops")
    optimization_score: float = Field(default=0.0, description="Optimization score (0-1)")
    metrics: RouteMetrics = Field(default_factory=RouteMetrics)
    assigned_at: Optional[datetime] = Field(default=None, description="When route was assigned")
    started_at: Optional[datetime] = Field(default=None, description="When route was started")
    completed_at: Optional[datetime] = Field(default=None, description="When route was completed")
    created_at: datetime
    updated_at: datetime
    stops: List[RouteStop] = Field(default_factory=list, description="Route stops with full details")
    reoptimization_history: List[Dict[str, Any]] = Field(default_factory=list, description="Reoptimization history")


class RouteUpdate(BaseModel):
    """Update route request."""
    name: Optional[str] = None
    warehouse_id: Optional[str] = None
    date: Optional[date] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    status: Optional[RouteStatus] = None
    constraints: Optional[RouteConstraints] = None


class RouteListResponse(BaseModel):
    """List routes response."""
    routes: List[Route]
    total: int
    limit: int
    offset: int


class DriverInfo(BaseModel):
    """Driver information for route assignment."""
    driver_id: str
    available_start: time
    available_end: time
    hos_remaining_minutes: float
    skills: List[str] = Field(default_factory=list)


class VehicleInfo(BaseModel):
    """Vehicle information for route assignment."""
    vehicle_id: str
    capacity_cubic_feet: float
    capacity_weight_lbs: float
    fuel_type: str = "diesel"
    fuel_efficiency_mpg: float = 10.0


class RouteOptimizationRequest(BaseModel):
    """Request to optimize routes."""
    warehouse_id: str = Field(..., description="Origin warehouse ID")
    date: date = Field(..., description="Route date")
    stops: List[RouteStopCreate] = Field(..., description="Stops to optimize")
    drivers: List[DriverInfo] = Field(default_factory=list, description="Available drivers")
    vehicles: List[VehicleInfo] = Field(default_factory=list, description="Available vehicles")
    constraints: RouteConstraints = Field(default_factory=RouteConstraints)
    optimization_options: Dict[str, Any] = Field(default_factory=dict, description="Optimization options")


class OptimizedRoute(BaseModel):
    """Optimized route result."""
    id: str
    stops: List[RouteStop]
    metrics: RouteMetrics
    optimization_score: float
    unassigned_stops: List[RouteStopCreate] = Field(default_factory=list)


class RouteOptimizationResponse(BaseModel):
    """Response from route optimization."""
    routes: List[OptimizedRoute]
    unassigned_stops: List[RouteStopCreate] = Field(default_factory=list)
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")


class RouteReoptimizationRequest(BaseModel):
    """Request to re-optimize a route."""
    trigger: ReoptimizationTrigger = Field(..., description="Trigger for re-optimization")
    new_stop: Optional[RouteStopCreate] = Field(default=None, description="New stop to add")
    removed_stop_ids: List[str] = Field(default_factory=list, description="Stop IDs to remove")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class RouteReoptimizationResponse(BaseModel):
    """Response from route re-optimization."""
    route_id: str
    optimized_route: OptimizedRoute
    changes: str = Field(..., description="Description of changes made")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")


class RouteAssignment(BaseModel):
    """Route assignment request."""
    driver_id: str = Field(..., description="Driver ID to assign")
    vehicle_id: str = Field(..., description="Vehicle ID to assign")
    start_time: Optional[time] = Field(default=None, description="Start time")


class RouteAssignmentResponse(BaseModel):
    """Response from route assignment."""
    route_id: str
    driver_id: str
    vehicle_id: str
    assigned_at: datetime
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")


class RouteStats(BaseModel):
    """Route statistics."""
    total_routes: int
    pending_routes: int
    assigned_routes: int
    in_progress_routes: int
    completed_routes: int
    avg_optimization_score: float
    avg_distance_miles: float
    avg_duration_minutes: float
    total_stops: int


class StopActionRequest(BaseModel):
    """Request to perform an action on a stop."""
    reason: Optional[str] = Field(default=None, description="Reason for action")


class StopActionResponse(BaseModel):
    """Response from stop action."""
    stop_id: str
    route_id: str
    action: str
    timestamp: datetime
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")
