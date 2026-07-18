"""
Schemas for the Inventory Management Agent.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.shared_types.schemas import AgentType, TrustLevel


class InventoryStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    QUARANTINED = "quarantined"


class AdjustmentType(str, Enum):
    RECEIPT = "receipt"
    ISSUE = "issue"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"
    SHRINKAGE = "shrinkage"
    DAMAGE = "damage"


class InventoryPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Location(BaseModel):
    """Location model."""
    address: Optional[str] = None
    aisle: Optional[str] = None
    shelf: Optional[str] = None
    bin: Optional[str] = None
    
    def to_string(self) -> str:
        parts = [self.address, self.aisle, self.shelf, self.bin]
        return " ".join(filter(None, parts))


class InventoryMetadata(BaseModel):
    """Inventory item metadata."""
    weight_lbs: Optional[float] = None
    dimensions: Optional[Dict[str, float]] = None
    unit_of_measure: Optional[str] = None
    category: Optional[str] = None
    supplier_sku: Optional[str] = None
    min_order_quantity: Optional[int] = None
    lead_time_days: Optional[int] = None


class InventoryItemBase(BaseModel):
    """Base inventory item model."""
    sku: str = Field(..., description="Stock Keeping Unit")
    name: str = Field(..., description="Item name")
    description: Optional[str] = Field(default=None, description="Item description")
    category: Optional[str] = Field(default=None, description="Item category")
    warehouse_id: Optional[str] = Field(default=None, description="Warehouse ID")
    location: Optional[Location] = Field(default=None, description="Storage location")
    quantity_on_hand: int = Field(default=0, ge=0, description="Current quantity on hand")
    quantity_reserved: int = Field(default=0, ge=0, description="Quantity reserved for orders")
    reorder_point: int = Field(default=0, ge=0, description="Reorder point")
    reorder_quantity: int = Field(default=0, ge=0, description="Reorder quantity")
    unit_cost: float = Field(default=0.0, ge=0.0, description="Unit cost")
    unit_of_measure: str = Field(default="each", description="Unit of measure")
    low_stock_alert: bool = Field(default=False, description="Low stock alert flag")
    expiry_date: Optional[datetime] = Field(default=None, description="Expiration date")
    batch_number: Optional[str] = Field(default=None, description="Batch/lot number")
    status: InventoryStatus = Field(default=InventoryStatus.ACTIVE, description="Item status")
    metadata: InventoryMetadata = Field(default_factory=InventoryMetadata)


class InventoryItemCreate(InventoryItemBase):
    """Create inventory item request."""
    pass


class InventoryItem(InventoryItemBase):
    """Full inventory item model."""
    id: str
    tenant_id: str
    supplier_id: Optional[str] = Field(default=None, description="Supplier ID")
    quantity_available: int = Field(default=0, description="Available quantity (on_hand - reserved)")
    last_updated: Optional[datetime] = Field(default=None, description="Last update timestamp")
    created_at: datetime
    updated_at: datetime
    
    @property
    def available_quantity(self) -> int:
        return self.quantity_on_hand - self.quantity_reserved


class InventoryItemUpdate(BaseModel):
    """Update inventory item request."""
    sku: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    warehouse_id: Optional[str] = None
    location: Optional[Location] = None
    reorder_point: Optional[int] = None
    reorder_quantity: Optional[int] = None
    unit_cost: Optional[float] = None
    unit_of_measure: Optional[str] = None
    low_stock_alert: Optional[bool] = None
    expiry_date: Optional[datetime] = None
    batch_number: Optional[str] = None
    status: Optional[InventoryStatus] = None
    metadata: Optional[InventoryMetadata] = None


class InventoryMovement(BaseModel):
    """Inventory movement model."""
    id: str
    inventory_item_id: str
    adjustment_type: AdjustmentType
    quantity: int
    reference: Optional[str] = Field(default=None, description="Reference number")
    user_id: Optional[str] = Field(default=None, description="User who made the adjustment")
    notes: Optional[str] = Field(default=None, description="Additional notes")
    timestamp: datetime
    
    @property
    def is_positive(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_negative(self) -> bool:
        return self.quantity < 0


class InventoryAdjustment(BaseModel):
    """Inventory adjustment request."""
    adjustment_type: AdjustmentType = Field(..., description="Type of adjustment")
    quantity: int = Field(..., description="Quantity to adjust (positive or negative)")
    reference: Optional[str] = Field(default=None, description="Reference number")
    notes: Optional[str] = Field(default=None, description="Additional notes")
    target_warehouse_id: Optional[str] = Field(default=None, description="Target warehouse for transfers")


class InventoryReservation(BaseModel):
    """Inventory reservation model."""
    reservation_id: str
    order_id: Optional[str] = Field(default=None, description="Order ID")
    quantity: int = Field(..., description="Quantity to reserve")
    
    @property
    def is_valid(self) -> bool:
        return self.quantity > 0


class InventoryRelease(BaseModel):
    """Inventory release model."""
    reservation_id: str = Field(..., description="Reservation ID to release")
    quantity: Optional[int] = Field(default=None, description="Quantity to release (default: all)")


class ReplenishmentRecommendation(BaseModel):
    """Replenishment recommendation model."""
    item_id: str
    sku: str
    current_quantity: int
    recommended_order_quantity: int
    urgency: InventoryPriority
    lead_time_days: int
    estimated_cost: float
    reason: str


class ReplenishmentRequest(BaseModel):
    """Replenishment request."""
    warehouse_id: Optional[str] = Field(default=None, description="Filter by warehouse")
    category: Optional[str] = Field(default=None, description="Filter by category")
    horizon_days: int = Field(default=30, description="Forecast horizon in days")


class DiscrepancyReport(BaseModel):
    """Discrepancy report model."""
    item_id: str = Field(..., description="Inventory item ID")
    expected_quantity: int = Field(..., description="Expected quantity")
    actual_quantity: int = Field(..., description="Actual quantity")
    discrepancy_type: str = Field(..., description="Type of discrepancy")
    location: Optional[str] = Field(default=None, description="Location where discrepancy found")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class DiscrepancyResponse(BaseModel):
    """Discrepancy response."""
    discrepancy_id: str
    item_id: str
    status: str
    agent_task_id: Optional[str] = None


class InventoryListResponse(BaseModel):
    """List inventory items response."""
    items: List[InventoryItem]
    total: int
    limit: int
    offset: int


class MovementHistoryResponse(BaseModel):
    """Movement history response."""
    item_id: str
    movements: List[InventoryMovement]
    total: int


class InventoryStats(BaseModel):
    """Inventory statistics."""
    total_items: int
    total_quantity: int
    total_value: float
    low_stock_items: int
    out_of_stock_items: int
    by_category: Dict[str, int]
    by_warehouse: Dict[str, int]


class LowStockAlert(BaseModel):
    """Low stock alert."""
    item_id: str
    sku: str
    name: str
    current_quantity: int
    reorder_point: int
    quantity_below: int
    warehouse_id: Optional[str]
    location: Optional[str]
