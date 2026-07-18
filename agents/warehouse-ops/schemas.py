"""
Pydantic schemas for the Warehouse Operations Agent.
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class WarehouseTaskType(str, Enum):
    """Types of warehouse tasks."""
    PICK = "pick"
    PACK = "pack"
    RECEIVE = "receive"
    PUTAWAY = "putaway"
    COUNT = "count"
    MOVE = "move"


class WarehouseTaskStatus(str, Enum):
    """Status of warehouse tasks."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WarehouseTaskPriority(str, Enum):
    """Priority levels for warehouse tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DockSlotStatus(str, Enum):
    """Status of dock slots."""
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_USE = "in_use"
    COMPLETED = "completed"


# ============================================================================
# Warehouse Task Schemas
# ============================================================================

class WarehouseTaskBase(BaseModel):
    """Base schema for warehouse tasks."""
    warehouse_id: str = Field(..., description="ID of the warehouse")
    task_type: WarehouseTaskType = Field(..., description="Type of task")
    priority: WarehouseTaskPriority = Field(default=WarehouseTaskPriority.MEDIUM)
    description: str = Field(..., description="Description of the task")
    location: str = Field(..., description="Location in the warehouse")
    order_id: Optional[str] = Field(default=None, description="Related order ID")
    shipment_id: Optional[str] = Field(default=None, description="Related shipment ID")
    inventory_item_id: Optional[str] = Field(default=None, description="Related inventory item ID")
    quantity: Optional[int] = Field(default=None, description="Quantity to handle")
    estimated_duration_minutes: int = Field(default=0, ge=0, description="Estimated duration in minutes")
    due_at: Optional[datetime] = Field(default=None, description="Due date/time")


class WarehouseTaskCreate(WarehouseTaskBase):
    """Schema for creating a warehouse task."""
    pass


class WarehouseTask(WarehouseTaskBase):
    """Full schema for warehouse tasks."""
    id: str = Field(..., description="Unique task ID")
    tenant_id: str = Field(..., description="Tenant ID")
    status: WarehouseTaskStatus = Field(default=WarehouseTaskStatus.PENDING)
    assigned_to: Optional[str] = Field(default=None, description="User ID assigned to this task")
    actual_duration_minutes: Optional[int] = Field(default=None, description="Actual duration in minutes")
    created_at: datetime = Field(..., description="When the task was created")
    updated_at: datetime = Field(..., description="When the task was last updated")

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v):
        if isinstance(v, str) and v.startswith('task_'):
            return v
        return f"task_{v}" if isinstance(v, str) else v


class WarehouseTaskUpdate(BaseModel):
    """Schema for updating a warehouse task."""
    status: Optional[WarehouseTaskStatus] = None
    assigned_to: Optional[str] = None
    priority: Optional[WarehouseTaskPriority] = None
    description: Optional[str] = None
    location: Optional[str] = None
    due_at: Optional[datetime] = None
    actual_duration_minutes: Optional[int] = None


class WarehouseTaskListResponse(BaseModel):
    """Response for listing warehouse tasks."""
    tasks: List[WarehouseTask] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


# ============================================================================
# Task Optimization Schemas
# ============================================================================

class WorkerInfo(BaseModel):
    """Information about a warehouse worker."""
    user_id: str = Field(..., description="User ID")
    skills: List[str] = Field(default_factory=list, description="Worker skills")
    available_start: Optional[time] = Field(default=None, description="Available start time")
    available_end: Optional[time] = Field(default=None, description="Available end time")


class TaskOptimizationRequest(BaseModel):
    """Request to optimize task sequencing."""
    warehouse_id: str = Field(..., description="Warehouse ID")
    task_ids: List[str] = Field(default_factory=list, description="List of task IDs to optimize")
    workers: List[WorkerInfo] = Field(default_factory=list, description="List of available workers")
    constraints: Optional[Dict[str, Any]] = Field(default=None, description="Optimization constraints")


class OptimizedTaskAssignment(BaseModel):
    """Optimized task assignment."""
    task_id: str = Field(..., description="Task ID")
    sequence: int = Field(..., description="Sequence number")
    assigned_to: Optional[str] = Field(default=None, description="User ID assigned to")
    start_time: Optional[time] = Field(default=None, description="Start time")


class TaskOptimizationResponse(BaseModel):
    """Response for task optimization."""
    optimized_sequence: List[OptimizedTaskAssignment] = Field(
        default_factory=list,
        description="Optimized sequence of tasks"
    )
    unassigned_tasks: List[str] = Field(
        default_factory=list,
        description="Tasks that could not be assigned"
    )
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this optimization")


# ============================================================================
# Dock Schedule Schemas
# ============================================================================

class DockSlotBase(BaseModel):
    """Base schema for dock slots."""
    start_time: time = Field(..., description="Start time of the slot")
    end_time: time = Field(..., description="End time of the slot")
    status: DockSlotStatus = Field(default=DockSlotStatus.AVAILABLE)
    shipment_id: Optional[str] = Field(default=None, description="Related shipment ID")
    carrier: Optional[str] = Field(default=None, description="Carrier name")
    vehicle_type: Optional[str] = Field(default=None, description="Vehicle type")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class DockSlot(DockSlotBase):
    """Full schema for dock slots."""
    id: str = Field(..., description="Unique slot ID")


class DockScheduleBase(BaseModel):
    """Base schema for dock schedules."""
    warehouse_id: str = Field(..., description="Warehouse ID")
    dock_number: str = Field(..., description="Dock number")
    date: date = Field(..., description="Date of the schedule")


class DockSchedule(DockScheduleBase):
    """Full schema for dock schedules."""
    id: str = Field(..., description="Unique schedule ID")
    slots: List[DockSlot] = Field(default_factory=list, description="List of dock slots")


class DockScheduleCreate(DockScheduleBase):
    """Schema for creating a dock schedule."""
    slots: List[DockSlotBase] = Field(default_factory=list, description="List of dock slots")


class DockScheduleListResponse(BaseModel):
    """Response for listing dock schedules."""
    schedules: List[DockSchedule] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


# ============================================================================
# Labor Forecast Schemas
# ============================================================================

class LaborForecastByType(BaseModel):
    """Labor forecast by task type."""
    pick: int = Field(default=0)
    pack: int = Field(default=0)
    receive: int = Field(default=0)
    putaway: int = Field(default=0)
    count: int = Field(default=0)
    move: int = Field(default=0)


class LaborForecastEntry(BaseModel):
    """Single labor forecast entry."""
    date: date = Field(..., description="Forecast date")
    estimated_tasks: int = Field(default=0, description="Estimated number of tasks")
    estimated_hours: float = Field(default=0.0, description="Estimated hours needed")
    recommended_workers: int = Field(default=0, description="Recommended number of workers")
    by_task_type: LaborForecastByType = Field(
        default_factory=LaborForecastByType,
        description="Breakdown by task type"
    )


class LaborForecastRequest(BaseModel):
    """Request to generate labor forecast."""
    warehouse_id: str = Field(..., description="Warehouse ID")
    start_date: date = Field(..., description="Start date for forecast")
    end_date: date = Field(..., description="End date for forecast")
    historical_data_days: int = Field(default=30, ge=1, le=365, description="Historical data days to use")


class LaborForecastResponse(BaseModel):
    """Response for labor forecast."""
    forecast: List[LaborForecastEntry] = Field(default_factory=list, description="Labor forecast")
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this forecast")


# ============================================================================
# Stats and Metrics Schemas
# ============================================================================

class WarehouseStats(BaseModel):
    """Statistics for warehouse operations."""
    total_tasks: int = Field(default=0)
    pending_tasks: int = Field(default=0)
    in_progress_tasks: int = Field(default=0)
    completed_tasks: int = Field(default=0)
    overdue_tasks: int = Field(default=0)
    avg_completion_time_minutes: float = Field(default=0.0)
    task_completion_rate: float = Field(default=0.0)
    dock_utilization_rate: float = Field(default=0.0)


class WarehouseOpsStats(BaseModel):
    """Overall warehouse operations statistics."""
    by_warehouse: Dict[str, WarehouseStats] = Field(default_factory=dict)
    total_tasks: int = Field(default=0)
    avg_completion_rate: float = Field(default=0.0)
    forecast_accuracy: Optional[float] = Field(default=None)
