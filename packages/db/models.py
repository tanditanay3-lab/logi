"""
SQLAlchemy models for Lanework database.

All models include tenant_id for row-level security.
"""

import enum
from datetime import datetime, date, time
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship, sessionmaker, validates
from sqlalchemy.sql import expression

Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================

class AgentTaskStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_EXECUTED = "auto_executed"
    FAILED = "failed"
    COMPLETED = "completed"


class AgentType(str, enum.Enum):
    SHIPMENT_TRACKING = "shipment-tracking"
    INVENTORY = "inventory"
    ROUTE_OPTIMIZATION = "route-optimization"
    WAREHOUSE_OPS = "warehouse-ops"
    FLEET_MANAGEMENT = "fleet-management"
    CUSTOMER_COMMUNICATION = "customer-communication"
    DEMAND_FORECASTING = "demand-forecasting"
    FREIGHT_PROCUREMENT = "freight-procurement"
    VOICE = "voice"


class TrustLevel(str, enum.Enum):
    PROPOSE_ONLY = "propose_only"
    AUTO_EXECUTE_LOW_RISK = "auto_execute_low_risk"
    FULLY_AUTONOMOUS = "fully_autonomous"


class ApprovalRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ConversationChannel(str, enum.Enum):
    CHAT = "chat"
    VOICE = "voice"


class VoiceCallDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class VoiceCallerType(str, enum.Enum):
    DRIVER = "driver"
    CUSTOMER = "customer"
    DISPATCHER = "dispatcher"
    UNKNOWN = "unknown"


class ShipmentStatus(str, enum.Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    DELAYED = "delayed"


class InventoryStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    QUARANTINED = "quarantined"


class RouteStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RouteStopStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class RouteStopType(str, enum.Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    BOTH = "both"


class DriverStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class VehicleStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class VehicleType(str, enum.Enum):
    TRUCK = "truck"
    VAN = "van"
    CARGO_VAN = "cargo_van"
    BOX_TRUCK = "box_truck"
    SEMI = "semi"


class WarehouseTaskType(str, enum.Enum):
    PICK = "pick"
    PACK = "pack"
    RECEIVE = "receive"
    PUTAWAY = "putaway"
    COUNT = "count"
    MOVE = "move"


class WarehouseTaskStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WarehouseTaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DockSlotStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_USE = "in_use"
    COMPLETED = "completed"


class FreightQuoteStatus(str, enum.Enum):
    REQUESTED = "requested"
    RECEIVED = "received"
    EXPIRED = "expired"
    SELECTED = "selected"
    REJECTED = "rejected"


class CarrierType(str, enum.Enum):
    LTL = "ltl"
    FTL = "ftl"
    PARCEL = "parcel"
    COURIER = "courier"


class ForecastGranularity(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ============================================================================
# Mixins
# ============================================================================

class TenantMixin:
    """Mixin for tenant-specific models."""
    tenant_id = Column(String(64), nullable=False, index=True)


class TimestampMixin:
    """Mixin for models with timestamps."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)


class IDMixin:
    """Mixin for models with UUID primary key."""
    id = Column(String(64), primary_key=True, default=lambda: str(uuid4())[:12])


# ============================================================================
# Core Models
# ============================================================================

class Tenant(TimestampMixin, Base):
    """Tenant model for multi-tenancy."""
    __tablename__ = "tenants"
    
    id = Column(String(64), primary_key=True, default=lambda: f"tenant_{str(uuid4())[:8]}")
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False)
    status = Column(String(32), default="active")
    config = Column(JSONB, default={})
    
    # Row-level security policy
    __table_args__ = (
        Index('ix_tenant_slug', 'slug', unique=True),
    )


class User(TimestampMixin, Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(String(64), primary_key=True, default=lambda: f"user_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    role = Column(String(64), default="user")
    status = Column(String(32), default="active")
    last_login = Column(DateTime(timezone=True))
    
    tenant = relationship("Tenant", backref="users")
    
    __table_args__ = (
        Index('ix_user_tenant_email', 'tenant_id', 'email', unique=True),
    )


# ============================================================================
# Agent Models
# ============================================================================

class AgentTask(TimestampMixin, Base):
    """AgentTask model for tracking all agent actions."""
    __tablename__ = "agent_tasks"
    
    id = Column(String(64), primary_key=True, default=lambda: f"task_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    agent_type = Column(Enum(AgentType), nullable=False, index=True)
    action_type = Column(String(255), nullable=False)
    status = Column(Enum(AgentTaskStatus), default=AgentTaskStatus.PENDING_APPROVAL, index=True)
    trust_level = Column(Enum(TrustLevel), default=TrustLevel.PROPOSE_ONLY)
    reasoning_trace = Column(Text)
    input_data = Column(JSONB, default={})
    output_data = Column(JSONB)
    approval_request_id = Column(String(64), ForeignKey('approval_requests.id'))
    related_entity_id = Column(String(64))
    related_entity_type = Column(String(64))
    error_message = Column(Text)
    completed_at = Column(DateTime(timezone=True))
    
    tenant = relationship("Tenant", backref="agent_tasks")
    approval_request = relationship("ApprovalRequest", backref="agent_task")
    
    __table_args__ = (
        Index('ix_agent_task_tenant_status', 'tenant_id', 'status'),
        Index('ix_agent_task_tenant_agent', 'tenant_id', 'agent_type'),
        Index('ix_agent_task_related', 'related_entity_type', 'related_entity_id'),
    )


class ApprovalRequest(TimestampMixin, Base):
    """ApprovalRequest model for tracking approval workflows."""
    __tablename__ = "approval_requests"
    
    id = Column(String(64), primary_key=True, default=lambda: f"approval_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    agent_task_id = Column(String(64), ForeignKey('agent_tasks.id'), nullable=False)
    agent_type = Column(Enum(AgentType), nullable=False)
    action_description = Column(Text, nullable=False)
    status = Column(Enum(ApprovalRequestStatus), default=ApprovalRequestStatus.PENDING, index=True)
    requested_by = Column(String(64), nullable=False)
    approved_by = Column(String(64), ForeignKey('users.id'))
    rejected_by = Column(String(64), ForeignKey('users.id'))
    rejection_reason = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    
    tenant = relationship("Tenant", backref="approval_requests")
    approved_user = relationship("User", foreign_keys=[approved_by], backref="approved_requests")
    rejected_user = relationship("User", foreign_keys=[rejected_by], backref="rejected_requests")
    
    __table_args__ = (
        Index('ix_approval_tenant_status', 'tenant_id', 'status'),
        Index('ix_approval_agent_task', 'agent_task_id'),
    )


class Conversation(TimestampMixin, Base):
    """Conversation model for chat and voice interactions."""
    __tablename__ = "conversations"
    
    id = Column(String(64), primary_key=True, default=lambda: f"conv_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    channel = Column(Enum(ConversationChannel), nullable=False, index=True)
    participant_type = Column(String(64), nullable=False)
    participant_id = Column(String(64))
    messages = Column(JSONB, default=[])
    related_agent_task_ids = Column(ARRAY(String(64)), default=[])
    voice_call_id = Column(String(64), ForeignKey('voice_calls.id'))
    
    tenant = relationship("Tenant", backref="conversations")
    voice_call = relationship("VoiceCall", backref="conversation")
    
    __table_args__ = (
        Index('ix_conversation_tenant_channel', 'tenant_id', 'channel'),
        Index('ix_conversation_participant', 'participant_type', 'participant_id'),
    )


class VoiceCall(TimestampMixin, Base):
    """VoiceCall model for voice interactions."""
    __tablename__ = "voice_calls"
    
    id = Column(String(64), primary_key=True, default=lambda: f"call_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    direction = Column(Enum(VoiceCallDirection), nullable=False, index=True)
    caller_type = Column(Enum(VoiceCallerType), default=VoiceCallerType.UNKNOWN)
    phone_number = Column(String(32), nullable=False)
    transcript = Column(Text)
    structured_intent = Column(JSONB)
    duration_seconds = Column(Integer)
    escalated_to_human = Column(Boolean, default=False)
    recording_url = Column(String(512))
    related_agent_task_ids = Column(ARRAY(String(64)), default=[])
    ended_at = Column(DateTime(timezone=True))
    
    tenant = relationship("Tenant", backref="voice_calls")
    
    __table_args__ = (
        Index('ix_voice_call_tenant_direction', 'tenant_id', 'direction'),
        Index('ix_voice_call_phone', 'phone_number'),
        Index('ix_voice_call_timestamp', 'created_at'),
    )


# ============================================================================
# Shipment Tracking Models
# ============================================================================

class Shipment(TimestampMixin, Base):
    """Shipment model for tracking shipments."""
    __tablename__ = "shipments"
    
    id = Column(String(64), primary_key=True, default=lambda: f"shipment_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    tracking_number = Column(String(128), index=True)
    carrier = Column(String(128))
    carrier_service = Column(String(128))
    status = Column(Enum(ShipmentStatus), default=ShipmentStatus.PENDING, index=True)
    origin = Column(JSONB)
    destination = Column(JSONB)
    estimated_delivery = Column(DateTime(timezone=True))
    actual_delivery = Column(DateTime(timezone=True))
    current_location = Column(JSONB)
    eta_drift_minutes = Column(Float)
    eta_drift_detected_at = Column(DateTime(timezone=True))
    metadata = Column(JSONB, default={})
    carrier_account = Column(String(128))
    billing_reference = Column(String(128))
    notes = Column(Text)
    
    tenant = relationship("Tenant", backref="shipments")
    events = relationship("ShipmentEvent", backref="shipment", order_by="ShipmentEvent.timestamp")
    
    __table_args__ = (
        Index('ix_shipment_tenant_tracking', 'tenant_id', 'tracking_number', unique=True),
        Index('ix_shipment_tenant_status', 'tenant_id', 'status'),
        Index('ix_shipment_carrier', 'carrier'),
        Index('ix_shipment_eta_drift', 'eta_drift_minutes'),
    )


class ShipmentEvent(TimestampMixin, Base):
    """ShipmentEvent model for tracking shipment events."""
    __tablename__ = "shipment_events"
    
    id = Column(String(64), primary_key=True, default=lambda: f"evt_{str(uuid4())[:8]}")
    shipment_id = Column(String(64), ForeignKey('shipments.id'), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    event_type = Column(String(128), nullable=False)
    description = Column(Text)
    location = Column(JSONB)
    carrier_timestamp = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('ix_shipment_event_shipment', 'shipment_id', 'timestamp'),
    )


# ============================================================================
# Inventory Models
# ============================================================================

class Warehouse(TimestampMixin, Base):
    """Warehouse model."""
    __tablename__ = "warehouses"
    
    id = Column(String(64), primary_key=True, default=lambda: f"warehouse_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(JSONB)
    status = Column(String(32), default="active")
    config = Column(JSONB, default={})
    
    tenant = relationship("Tenant", backref="warehouses")
    
    __table_args__ = (
        Index('ix_warehouse_tenant_name', 'tenant_id', 'name', unique=True),
    )


class InventoryItem(TimestampMixin, Base):
    """InventoryItem model."""
    __tablename__ = "inventory_items"
    
    id = Column(String(64), primary_key=True, default=lambda: f"inventory_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    warehouse_id = Column(String(64), ForeignKey('warehouses.id'), index=True)
    sku = Column(String(128), nullable=False, index=True)
    name = Column(String(255))
    description = Column(Text)
    category = Column(String(128))
    location = Column(String(255))
    quantity_on_hand = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    quantity_available = Column(Integer, default=0)
    reorder_point = Column(Integer, default=0)
    reorder_quantity = Column(Integer, default=0)
    unit_cost = Column(Numeric(10, 2), default=0)
    unit_of_measure = Column(String(32))
    last_updated = Column(DateTime(timezone=True))
    low_stock_alert = Column(Boolean, default=False)
    expiry_date = Column(Date)
    batch_number = Column(String(128))
    status = Column(Enum(InventoryStatus), default=InventoryStatus.ACTIVE)
    supplier_id = Column(String(64))
    
    tenant = relationship("Tenant", backref="inventory_items")
    warehouse = relationship("Warehouse", backref="inventory_items")
    movements = relationship("InventoryMovement", backref="inventory_item")
    
    __table_args__ = (
        Index('ix_inventory_tenant_warehouse_sku', 'tenant_id', 'warehouse_id', 'sku', unique=True),
        Index('ix_inventory_tenant_category', 'tenant_id', 'category'),
        Index('ix_inventory_low_stock', 'tenant_id', 'low_stock_alert'),
    )


class InventoryMovement(TimestampMixin, Base):
    """InventoryMovement model for tracking inventory changes."""
    __tablename__ = "inventory_movements"
    
    id = Column(String(64), primary_key=True, default=lambda: f"movement_{str(uuid4())[:8]}")
    inventory_item_id = Column(String(64), ForeignKey('inventory_items.id'), nullable=False, index=True)
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    adjustment_type = Column(String(64), nullable=False)
    quantity = Column(Integer, nullable=False)
    reference = Column(String(255))
    user_id = Column(String(64), ForeignKey('users.id'))
    notes = Column(Text)
    
    tenant = relationship("Tenant", backref="inventory_movements")
    user = relationship("User", backref="inventory_movements")
    
    __table_args__ = (
        Index('ix_inventory_movement_item', 'inventory_item_id', 'created_at'),
    )


# ============================================================================
# Route Optimization Models
# ============================================================================

class Route(TimestampMixin, Base):
    """Route model."""
    __tablename__ = "routes"
    
    id = Column(String(64), primary_key=True, default=lambda: f"route_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    name = Column(String(255))
    status = Column(Enum(RouteStatus), default=RouteStatus.PENDING, index=True)
    driver_id = Column(String(64), ForeignKey('drivers.id'))
    vehicle_id = Column(String(64), ForeignKey('vehicles.id'))
    warehouse_id = Column(String(64), ForeignKey('warehouses.id'))
    date = Column(Date)
    total_distance_miles = Column(Float)
    total_duration_minutes = Column(Integer)
    total_stops = Column(Integer)
    optimization_score = Column(Float)
    constraints = Column(JSONB, default={})
    metrics = Column(JSONB, default={})
    assigned_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    tenant = relationship("Tenant", backref="routes")
    driver = relationship("Driver", backref="routes")
    vehicle = relationship("Vehicle", backref="routes")
    warehouse = relationship("Warehouse", backref="routes")
    stops = relationship("RouteStop", backref="route", order_by="RouteStop.sequence")
    reoptimization_history = relationship("RouteReoptimization", backref="route")
    
    __table_args__ = (
        Index('ix_route_tenant_status', 'tenant_id', 'status'),
        Index('ix_route_driver', 'driver_id'),
        Index('ix_route_vehicle', 'vehicle_id'),
        Index('ix_route_date', 'date'),
    )


class RouteStop(TimestampMixin, Base):
    """RouteStop model."""
    __tablename__ = "route_stops"
    
    id = Column(String(64), primary_key=True, default=lambda: f"stop_{str(uuid4())[:8]}")
    route_id = Column(String(64), ForeignKey('routes.id'), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    location = Column(JSONB, nullable=False)
    stop_type = Column(Enum(RouteStopType), nullable=False)
    time_window_start = Column(Time)
    time_window_end = Column(Time)
    estimated_arrival = Column(Time)
    actual_arrival = Column(Time)
    estimated_departure = Column(Time)
    actual_departure = Column(Time)
    shipment_ids = Column(ARRAY(String(64)), default=[])
    status = Column(Enum(RouteStopStatus), default=RouteStopStatus.PENDING)
    notes = Column(Text)
    
    __table_args__ = (
        Index('ix_route_stop_route_seq', 'route_id', 'sequence', unique=True),
        Index('ix_route_stop_status', 'status'),
    )


class RouteReoptimization(TimestampMixin, Base):
    """RouteReoptimization model for tracking route re-optimizations."""
    __tablename__ = "route_reoptimizations"
    
    id = Column(String(64), primary_key=True, default=lambda: f"reopt_{str(uuid4())[:8]}")
    route_id = Column(String(64), ForeignKey('routes.id'), nullable=False, index=True)
    trigger = Column(String(64), nullable=False)
    changes = Column(Text)
    agent_task_id = Column(String(64), ForeignKey('agent_tasks.id'))
    
    __table_args__ = (
        Index('ix_route_reopt_route', 'route_id', 'created_at'),
    )


# ============================================================================
# Fleet Management Models
# ============================================================================

class Driver(TimestampMixin, Base):
    """Driver model."""
    __tablename__ = "drivers"
    
    id = Column(String(64), primary_key=True, default=lambda: f"driver_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    license_number = Column(String(128))
    license_state = Column(String(64))
    license_expiry = Column(Date)
    status = Column(Enum(DriverStatus), default=DriverStatus.ACTIVE, index=True)
    home_warehouse_id = Column(String(64), ForeignKey('warehouses.id'))
    skills = Column(ARRAY(String(64)), default=[])
    phone = Column(String(32))
    email = Column(String(255))
    current_vehicle_id = Column(String(64), ForeignKey('vehicles.id'))
    assigned_route_id = Column(String(64), ForeignKey('routes.id'))
    
    tenant = relationship("Tenant", backref="drivers")
    home_warehouse = relationship("Warehouse", foreign_keys=[home_warehouse_id], backref="drivers")
    current_vehicle = relationship("Vehicle", foreign_keys=[current_vehicle_id], backref="current_driver")
    assigned_route = relationship("Route", foreign_keys=[assigned_route_id], backref="assigned_driver")
    hos_records = relationship("DriverHOSRecord", backref="driver")
    violations = relationship("DriverViolation", backref="driver")
    
    __table_args__ = (
        Index('ix_driver_tenant_name', 'tenant_id', 'name', unique=True),
        Index('ix_driver_license', 'license_number', unique=True),
        Index('ix_driver_status', 'status'),
    )


class DriverHOSRecord(TimestampMixin, Base):
    """DriverHOSRecord model for tracking HOS records."""
    __tablename__ = "driver_hos_records"
    
    id = Column(String(64), primary_key=True, default=lambda: f"hos_{str(uuid4())[:8]}")
    driver_id = Column(String(64), ForeignKey('drivers.id'), nullable=False, index=True)
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    duration_minutes = Column(Integer)
    location = Column(JSONB)
    notes = Column(Text)
    
    __table_args__ = (
        Index('ix_driver_hos_driver', 'driver_id', 'created_at'),
    )


class DriverViolation(TimestampMixin, Base):
    """DriverViolation model for tracking HOS violations."""
    __tablename__ = "driver_violations"
    
    id = Column(String(64), primary_key=True, default=lambda: f"violation_{str(uuid4())[:8]}")
    driver_id = Column(String(64), ForeignKey('drivers.id'), nullable=False, index=True)
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    violation_type = Column(String(128), nullable=False)
    severity = Column(String(32), nullable=False)
    description = Column(Text)
    resolved = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('ix_driver_violation_driver', 'driver_id', 'created_at'),
    )


class Vehicle(TimestampMixin, Base):
    """Vehicle model."""
    __tablename__ = "vehicles"
    
    id = Column(String(64), primary_key=True, default=lambda: f"vehicle_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    vin = Column(String(64), unique=True)
    license_plate = Column(String(32), unique=True)
    vehicle_type = Column(Enum(VehicleType), nullable=False)
    status = Column(Enum(VehicleStatus), default=VehicleStatus.ACTIVE, index=True)
    home_warehouse_id = Column(String(64), ForeignKey('warehouses.id'))
    capacity_cubic_feet = Column(Float)
    capacity_weight_lbs = Column(Float)
    fuel_type = Column(String(32))
    fuel_efficiency_mpg = Column(Float)
    odometer = Column(Integer, default=0)
    
    tenant = relationship("Tenant", backref="vehicles")
    home_warehouse = relationship("Warehouse", foreign_keys=[home_warehouse_id], backref="vehicles")
    maintenance_records = relationship("VehicleMaintenance", backref="vehicle")
    
    __table_args__ = (
        Index('ix_vehicle_tenant_name', 'tenant_id', 'name', unique=True),
        Index('ix_vehicle_vin', 'vin'),
        Index('ix_vehicle_status', 'status'),
    )


class VehicleMaintenance(TimestampMixin, Base):
    """VehicleMaintenance model for tracking vehicle maintenance."""
    __tablename__ = "vehicle_maintenance"
    
    id = Column(String(64), primary_key=True, default=lambda: f"maint_{str(uuid4())[:8]}")
    vehicle_id = Column(String(64), ForeignKey('vehicles.id'), nullable=False, index=True)
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    maintenance_type = Column(String(64), nullable=False)
    description = Column(Text)
    odometer = Column(Integer)
    cost = Column(Numeric(10, 2))
    next_service_due_miles = Column(Integer)
    next_service_due_date = Column(Date)
    
    __table_args__ = (
        Index('ix_vehicle_maintenance_vehicle', 'vehicle_id', 'created_at'),
    )


# ============================================================================
# Customer Models
# ============================================================================

class Customer(TimestampMixin, Base):
    """Customer model."""
    __tablename__ = "customers"
    
    id = Column(String(64), primary_key=True, default=lambda: f"customer_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(32))
    address = Column(JSONB)
    account_number = Column(String(128))
    status = Column(String(32), default="active")
    
    tenant = relationship("Tenant", backref="customers")
    orders = relationship("Order", backref="customer")
    
    __table_args__ = (
        Index('ix_customer_tenant_email', 'tenant_id', 'email', unique=True),
        Index('ix_customer_account', 'account_number', unique=True),
    )


class Order(TimestampMixin, Base):
    """Order model."""
    __tablename__ = "orders"
    
    id = Column(String(64), primary_key=True, default=lambda: f"order_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    customer_id = Column(String(64), ForeignKey('customers.id'))
    order_number = Column(String(128), unique=True)
    status = Column(String(64), default="pending", index=True)
    items = Column(JSONB, default=[])
    total_amount = Column(Numeric(10, 2))
    shipping_address = Column(JSONB)
    billing_address = Column(JSONB)
    notes = Column(Text)
    
    tenant = relationship("Tenant", backref="orders")
    
    __table_args__ = (
        Index('ix_order_tenant_number', 'tenant_id', 'order_number', unique=True),
        Index('ix_order_customer', 'customer_id'),
        Index('ix_order_status', 'status'),
    )


# ============================================================================
# Demand Forecasting Models
# ============================================================================

class ForecastRecord(TimestampMixin, Base):
    """ForecastRecord model."""
    __tablename__ = "forecast_records"
    
    id = Column(String(64), primary_key=True, default=lambda: f"forecast_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    sku = Column(String(128), nullable=False, index=True)
    warehouse_id = Column(String(64), ForeignKey('warehouses.id'))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    granularity = Column(Enum(ForecastGranularity), default=ForecastGranularity.DAILY)
    forecast_values = Column(JSONB, default=[])
    model_version = Column(String(64))
    accuracy_score = Column(Float)
    
    tenant = relationship("Tenant", backref="forecast_records")
    warehouse = relationship("Warehouse", backref="forecast_records")
    
    __table_args__ = (
        Index('ix_forecast_tenant_sku', 'tenant_id', 'sku'),
        Index('ix_forecast_warehouse', 'warehouse_id'),
        Index('ix_forecast_dates', 'start_date', 'end_date'),
    )


# ============================================================================
# Freight Procurement Models
# ============================================================================

class Carrier(TimestampMixin, Base):
    """Carrier model."""
    __tablename__ = "carriers"
    
    id = Column(String(64), primary_key=True, default=lambda: f"carrier_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    carrier_type = Column(Enum(CarrierType), nullable=False)
    services = Column(ARRAY(String(64)), default=[])
    contact = Column(JSONB, default={})
    performance = Column(JSONB, default={})
    contract_terms = Column(JSONB, default={})
    status = Column(String(32), default="active")
    
    tenant = relationship("Tenant", backref="carriers")
    quotes = relationship("FreightQuote", backref="carrier")
    
    __table_args__ = (
        Index('ix_carrier_tenant_name', 'tenant_id', 'name', unique=True),
        Index('ix_carrier_type', 'carrier_type'),
    )


class FreightQuote(TimestampMixin, Base):
    """FreightQuote model."""
    __tablename__ = "freight_quotes"
    
    id = Column(String(64), primary_key=True, default=lambda: f"quote_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    shipment_id = Column(String(64), ForeignKey('shipments.id'))
    carrier_id = Column(String(64), ForeignKey('carriers.id'), nullable=False)
    carrier_name = Column(String(255))
    service_level = Column(String(64))
    transit_time_hours = Column(Float)
    cost = Column(Numeric(10, 2))
    currency = Column(String(3), default="USD")
    status = Column(Enum(FreightQuoteStatus), default=FreightQuoteStatus.REQUESTED, index=True)
    expires_at = Column(DateTime(timezone=True))
    requested_at = Column(DateTime(timezone=True))
    received_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    
    tenant = relationship("Tenant", backref="freight_quotes")
    shipment = relationship("Shipment", backref="freight_quotes")
    
    __table_args__ = (
        Index('ix_quote_tenant_status', 'tenant_id', 'status'),
        Index('ix_quote_shipment', 'shipment_id'),
        Index('ix_quote_carrier', 'carrier_id'),
    )


# ============================================================================
# Warehouse Operations Models
# ============================================================================

class WarehouseTask(TimestampMixin, Base):
    """WarehouseTask model."""
    __tablename__ = "warehouse_tasks"
    
    id = Column(String(64), primary_key=True, default=lambda: f"task_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    warehouse_id = Column(String(64), ForeignKey('warehouses.id'), nullable=False, index=True)
    task_type = Column(Enum(WarehouseTaskType), nullable=False)
    status = Column(Enum(WarehouseTaskStatus), default=WarehouseTaskStatus.PENDING, index=True)
    priority = Column(Enum(WarehouseTaskPriority), default=WarehouseTaskPriority.MEDIUM)
    description = Column(Text)
    location = Column(String(255))
    assigned_to = Column(String(64), ForeignKey('users.id'))
    order_id = Column(String(64), ForeignKey('orders.id'))
    shipment_id = Column(String(64), ForeignKey('shipments.id'))
    inventory_item_id = Column(String(64), ForeignKey('inventory_items.id'))
    quantity = Column(Integer)
    estimated_duration_minutes = Column(Integer)
    actual_duration_minutes = Column(Integer)
    due_at = Column(DateTime(timezone=True))
    
    tenant = relationship("Tenant", backref="warehouse_tasks")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id], backref="warehouse_tasks")
    assigned_user = relationship("User", foreign_keys=[assigned_to], backref="warehouse_tasks")
    order = relationship("Order", backref="warehouse_tasks")
    shipment = relationship("Shipment", foreign_keys=[shipment_id], backref="warehouse_tasks")
    inventory_item = relationship("InventoryItem", foreign_keys=[inventory_item_id], backref="warehouse_tasks")
    
    __table_args__ = (
        Index('ix_warehouse_task_tenant_status', 'tenant_id', 'status'),
        Index('ix_warehouse_task_warehouse', 'warehouse_id'),
        Index('ix_warehouse_task_priority', 'priority'),
    )


class DockSchedule(TimestampMixin, Base):
    """DockSchedule model."""
    __tablename__ = "dock_schedules"
    
    id = Column(String(64), primary_key=True, default=lambda: f"dock_{str(uuid4())[:8]}")
    tenant_id = Column(String(64), ForeignKey('tenants.id'), nullable=False, index=True)
    warehouse_id = Column(String(64), ForeignKey('warehouses.id'), nullable=False, index=True)
    dock_number = Column(String(32), nullable=False)
    date = Column(Date, nullable=False)
    
    tenant = relationship("Tenant", backref="dock_schedules")
    warehouse = relationship("Warehouse", backref="dock_schedules")
    slots = relationship("DockSlot", backref="dock_schedule")
    
    __table_args__ = (
        Index('ix_dock_schedule_warehouse_date', 'warehouse_id', 'date', unique=True),
    )


class DockSlot(TimestampMixin, Base):
    """DockSlot model."""
    __tablename__ = "dock_slots"
    
    id = Column(String(64), primary_key=True, default=lambda: f"slot_{str(uuid4())[:8]}")
    dock_schedule_id = Column(String(64), ForeignKey('dock_schedules.id'), nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(Enum(DockSlotStatus), default=DockSlotStatus.AVAILABLE)
    shipment_id = Column(String(64), ForeignKey('shipments.id'))
    carrier = Column(String(128))
    vehicle_type = Column(String(64))
    notes = Column(Text)
    
    shipment = relationship("Shipment", backref="dock_slots")
    
    __table_args__ = (
        Index('ix_dock_slot_schedule', 'dock_schedule_id', 'start_time'),
        Index('ix_dock_slot_status', 'status'),
    )


# ============================================================================
# Utility Functions
# ============================================================================

def get_db_session(database_url: str):
    """Create a database session factory."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    
    engine = create_async_engine(database_url, echo=False)
    
    async def get_session():
        async with AsyncSession(engine) as session:
            yield session
    
    return get_session


async def init_db(database_url: str):
    """Initialize the database."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    
    engine = create_async_engine(database_url, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()


def apply_tenant_filter(query, tenant_id: str, model_class):
    """Apply tenant filter to a query."""
    if hasattr(model_class, 'tenant_id'):
        return query.filter(model_class.tenant_id == tenant_id)
    return query
