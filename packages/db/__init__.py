"""
Database package for Lanework.

This package contains:
- SQLAlchemy models for all entities
- Database session management
- Row-level security utilities
- Migration utilities
"""

from .models import (
    # Base
    Base,
    
    # Core entities
    Tenant,
    User,
    
    # Agent entities
    AgentTask,
    ApprovalRequest,
    Conversation,
    VoiceCall,
    
    # Domain entities
    Shipment,
    ShipmentEvent,
    InventoryItem,
    InventoryMovement,
    Warehouse,
    Route,
    RouteStop,
    Driver,
    Vehicle,
    DriverHOSRecord,
    VehicleMaintenance,
    Customer,
    Order,
    ForecastRecord,
    FreightQuote,
    Carrier,
    WarehouseTask,
    DockSchedule,
    DockSlot,
    
    # Utility functions
    get_db_session,
    init_db,
    apply_tenant_filter,
)

__all__ = [
    "Base",
    "Tenant",
    "User",
    "AgentTask",
    "ApprovalRequest",
    "Conversation",
    "VoiceCall",
    "Shipment",
    "ShipmentEvent",
    "InventoryItem",
    "InventoryMovement",
    "Warehouse",
    "Route",
    "RouteStop",
    "Driver",
    "Vehicle",
    "DriverHOSRecord",
    "VehicleMaintenance",
    "Customer",
    "Order",
    "ForecastRecord",
    "FreightQuote",
    "Carrier",
    "WarehouseTask",
    "DockSchedule",
    "DockSlot",
    "get_db_session",
    "init_db",
    "apply_tenant_filter",
]
