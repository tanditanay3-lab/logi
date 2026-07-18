"""
Pydantic schemas for the Fleet & Driver Management Agent.
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class DriverStatus(str, Enum):
    """Status of a driver."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class VehicleStatus(str, Enum):
    """Status of a vehicle."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class VehicleType(str, Enum):
    """Type of vehicle."""
    TRUCK = "truck"
    VAN = "van"
    CARGO_VAN = "cargo_van"
    BOX_TRUCK = "box_truck"
    SEMI = "semi"


class HOSStatus(str, Enum):
    """HOS compliance status."""
    OK = "ok"
    WARNING = "warning"
    VIOLATION = "violation"


class MaintenanceStatus(str, Enum):
    """Maintenance status."""
    OK = "ok"
    WARNING = "warning"
    OVERDUE = "overdue"


class AlertSeverity(str, Enum):
    """Severity of compliance alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Type of compliance alerts."""
    HOS_VIOLATION = "hos_violation"
    MAINTENANCE_OVERDUE = "maintenance_overdue"
    LICENSE_EXPIRY = "license_expiry"


class HOSEventType(str, Enum):
    """Types of HOS events."""
    DUTY_ON = "duty_on"
    DUTY_OFF = "duty_off"
    DRIVE_START = "drive_start"
    DRIVE_END = "drive_end"
    BREAK_START = "break_start"
    BREAK_END = "break_end"


class MaintenanceType(str, Enum):
    """Types of maintenance."""
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    INSPECTION = "inspection"


# ============================================================================
# HOS Status Schema
# ============================================================================

class HOSStatus(BaseModel):
    """HOS (Hours of Service) status for a driver."""
    current_duty_hours: float = Field(default=0.0, description="Current duty hours")
    current_drive_hours: float = Field(default=0.0, description="Current drive hours")
    remaining_duty_hours: float = Field(default=0.0, description="Remaining duty hours")
    remaining_drive_hours: float = Field(default=0.0, description="Remaining drive hours")
    last_reset: Optional[datetime] = Field(default=None, description="Last reset timestamp")
    status: HOSStatus = Field(default=HOSStatus.OK, description="Overall HOS status")


# ============================================================================
# HOS Event Schema
# ============================================================================

class Location(BaseModel):
    """Location coordinates."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class HOSEventCreate(BaseModel):
    """Schema for creating an HOS event."""
    event_type: HOSEventType = Field(..., description="Type of HOS event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    duration_minutes: Optional[int] = Field(default=None, ge=0, description="Duration in minutes")
    location: Optional[Location] = Field(default=None, description="Location of the event")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class HOSEvent(HOSEventCreate):
    """Full schema for HOS events."""
    id: str = Field(..., description="Unique event ID")


# ============================================================================
# Driver Schemas
# ============================================================================

class DriverBase(BaseModel):
    """Base schema for drivers."""
    name: str = Field(..., description="Driver name")
    license_number: str = Field(..., description="Driver license number")
    license_state: str = Field(..., description="State of license issuance")
    license_expiry: date = Field(..., description="License expiry date")
    status: DriverStatus = Field(default=DriverStatus.ACTIVE, description="Driver status")
    home_warehouse_id: Optional[str] = Field(default=None, description="Home warehouse ID")
    skills: List[str] = Field(default_factory=list, description="Driver skills")
    phone: Optional[str] = Field(default=None, description="Phone number")
    email: Optional[str] = Field(default=None, description="Email address")


class DriverCreate(DriverBase):
    """Schema for creating a driver."""
    pass


class Driver(DriverBase):
    """Full schema for drivers."""
    id: str = Field(..., description="Unique driver ID")
    tenant_id: str = Field(..., description="Tenant ID")
    hos_status: HOSStatus = Field(default_factory=HOSStatus, description="Current HOS status")
    assigned_route_id: Optional[str] = Field(default=None, description="Currently assigned route ID")
    current_vehicle_id: Optional[str] = Field(default=None, description="Currently assigned vehicle ID")
    created_at: datetime = Field(..., description="When the driver was created")
    updated_at: datetime = Field(..., description="When the driver was last updated")

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v):
        if isinstance(v, str) and v.startswith('driver_'):
            return v
        return f"driver_{v}" if isinstance(v, str) else v


class DriverListResponse(BaseModel):
    """Response for listing drivers."""
    drivers: List[Driver] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class DriverUpdate(BaseModel):
    """Schema for updating a driver."""
    name: Optional[str] = None
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    license_expiry: Optional[date] = None
    status: Optional[DriverStatus] = None
    home_warehouse_id: Optional[str] = None
    skills: Optional[List[str]] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    assigned_route_id: Optional[str] = None
    current_vehicle_id: Optional[str] = None


# ============================================================================
# Vehicle Schemas
# ============================================================================

class MaintenanceStatus(BaseModel):
    """Maintenance status for a vehicle."""
    last_service: Optional[datetime] = Field(default=None, description="Last service date")
    next_service_due: Optional[datetime] = Field(default=None, description="Next service due date")
    next_service_miles: Optional[int] = Field(default=None, description="Next service due miles")
    status: MaintenanceStatus = Field(default=MaintenanceStatus.OK, description="Maintenance status")


class TelematicsData(BaseModel):
    """Telematics data for a vehicle."""
    device_id: Optional[str] = Field(default=None, description="Telematics device ID")
    last_location: Optional[Location] = Field(default=None, description="Last known location")
    last_update: Optional[datetime] = Field(default=None, description="Last update timestamp")
    speed_mph: Optional[float] = Field(default=None, description="Current speed in mph")
    engine_hours: Optional[float] = Field(default=None, description="Total engine hours")


class VehicleBase(BaseModel):
    """Base schema for vehicles."""
    name: str = Field(..., description="Vehicle name")
    vin: str = Field(..., description="Vehicle Identification Number")
    license_plate: str = Field(..., description="License plate number")
    vehicle_type: VehicleType = Field(..., description="Type of vehicle")
    status: VehicleStatus = Field(default=VehicleStatus.ACTIVE, description="Vehicle status")
    home_warehouse_id: Optional[str] = Field(default=None, description="Home warehouse ID")
    capacity_cubic_feet: Optional[float] = Field(default=None, description="Capacity in cubic feet")
    capacity_weight_lbs: Optional[float] = Field(default=None, description="Capacity in pounds")
    fuel_type: Optional[str] = Field(default=None, description="Fuel type")
    fuel_efficiency_mpg: Optional[float] = Field(default=None, description="Fuel efficiency in mpg")
    odometer: int = Field(default=0, ge=0, description="Current odometer reading")


class VehicleCreate(VehicleBase):
    """Schema for creating a vehicle."""
    pass


class Vehicle(VehicleBase):
    """Full schema for vehicles."""
    id: str = Field(..., description="Unique vehicle ID")
    tenant_id: str = Field(..., description="Tenant ID")
    maintenance_status: MaintenanceStatus = Field(
        default_factory=MaintenanceStatus,
        description="Maintenance status"
    )
    telematics: TelematicsData = Field(
        default_factory=TelematicsData,
        description="Telematics data"
    )
    created_at: datetime = Field(..., description="When the vehicle was created")
    updated_at: datetime = Field(..., description="When the vehicle was last updated")

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v):
        if isinstance(v, str) and v.startswith('vehicle_'):
            return v
        return f"vehicle_{v}" if isinstance(v, str) else v


class VehicleListResponse(BaseModel):
    """Response for listing vehicles."""
    vehicles: List[Vehicle] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class VehicleUpdate(BaseModel):
    """Schema for updating a vehicle."""
    name: Optional[str] = None
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    vehicle_type: Optional[VehicleType] = None
    status: Optional[VehicleStatus] = None
    home_warehouse_id: Optional[str] = None
    capacity_cubic_feet: Optional[float] = None
    capacity_weight_lbs: Optional[float] = None
    fuel_type: Optional[str] = None
    fuel_efficiency_mpg: Optional[float] = None
    odometer: Optional[int] = None


# ============================================================================
# Maintenance Schemas
# ============================================================================

class MaintenanceRecordCreate(BaseModel):
    """Schema for creating a maintenance record."""
    maintenance_type: MaintenanceType = Field(..., description="Type of maintenance")
    description: str = Field(..., description="Description of maintenance")
    odometer: int = Field(..., ge=0, description="Odometer reading at maintenance")
    cost: float = Field(default=0.0, ge=0, description="Cost of maintenance")
    next_service_due_miles: Optional[int] = Field(default=None, ge=0, description="Next service due miles")
    next_service_due_date: Optional[date] = Field(default=None, description="Next service due date")


class MaintenanceRecord(MaintenanceRecordCreate):
    """Full schema for maintenance records."""
    id: str = Field(..., description="Unique maintenance record ID")
    vehicle_id: str = Field(..., description="Vehicle ID")
    tenant_id: str = Field(..., description="Tenant ID")
    created_at: datetime = Field(..., description="When the record was created")
    updated_at: datetime = Field(..., description="When the record was last updated")


# ============================================================================
# HOS Compliance Check Schemas
# ============================================================================

class HOSComplianceCheckRequest(BaseModel):
    """Request to check HOS compliance for a route assignment."""
    route_id: str = Field(..., description="Route ID")
    estimated_duration_minutes: int = Field(..., ge=0, description="Estimated route duration in minutes")


class HOSComplianceCheckResponse(BaseModel):
    """Response for HOS compliance check."""
    driver_id: str = Field(..., description="Driver ID")
    route_id: str = Field(..., description="Route ID")
    compliant: bool = Field(..., description="Whether the assignment is compliant")
    remaining_hours_after: float = Field(..., description="Remaining hours after the route")
    warnings: List[str] = Field(default_factory=list, description="Compliance warnings")
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this check")


# ============================================================================
# Driver Assignment Schemas
# ============================================================================

class DriverVehicleAssignment(BaseModel):
    """Schema for assigning driver to vehicle."""
    vehicle_id: str = Field(..., description="Vehicle ID")
    route_id: Optional[str] = Field(default=None, description="Route ID")


class DriverVehicleAssignmentResponse(BaseModel):
    """Response for driver-vehicle assignment."""
    driver_id: str = Field(..., description="Driver ID")
    vehicle_id: str = Field(..., description="Vehicle ID")
    route_id: Optional[str] = Field(default=None, description="Route ID")
    assigned: bool = Field(..., description="Whether assignment was successful")
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this assignment")


# ============================================================================
# Compliance Alert Schemas
# ============================================================================

class ComplianceAlert(BaseModel):
    """Schema for compliance alerts."""
    id: str = Field(..., description="Unique alert ID")
    type: AlertType = Field(..., description="Alert type")
    severity: AlertSeverity = Field(..., description="Alert severity")
    entity_type: str = Field(..., description="Entity type (driver or vehicle)")
    entity_id: str = Field(..., description="Entity ID")
    description: str = Field(..., description="Alert description")
    timestamp: datetime = Field(..., description="Alert timestamp")
    acknowledged: bool = Field(default=False, description="Whether alert has been acknowledged")
    acknowledged_by: Optional[str] = Field(default=None, description="User ID who acknowledged")
    acknowledged_at: Optional[datetime] = Field(default=None, description="When alert was acknowledged")


class ComplianceAlertListResponse(BaseModel):
    """Response for listing compliance alerts."""
    alerts: List[ComplianceAlert] = Field(default_factory=list)


# ============================================================================
# Stats Schemas
# ============================================================================

class FleetStats(BaseModel):
    """Statistics for fleet management."""
    total_drivers: int = Field(default=0)
    active_drivers: int = Field(default=0)
    total_vehicles: int = Field(default=0)
    active_vehicles: int = Field(default=0)
    vehicles_in_maintenance: int = Field(default=0)
    hos_violations: int = Field(default=0)
    maintenance_overdue: int = Field(default=0)
    license_expiring_soon: int = Field(default=0)


class DriverStats(BaseModel):
    """Statistics for drivers."""
    total_hours_driven: float = Field(default=0.0)
    avg_hours_per_day: float = Field(default=0.0)
    violations_count: int = Field(default=0)
    on_time_delivery_rate: float = Field(default=0.0)
