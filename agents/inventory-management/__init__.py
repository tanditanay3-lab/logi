"""
Inventory Management Agent

This agent monitors stock across warehouses, predicts depletion, generates replenishment
recommendations, and reconciles discrepancies.
"""

from .main import app
from .schemas import (
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryAdjustment,
    InventoryReservation,
    InventoryRelease,
    ReplenishmentRecommendation,
    DiscrepancyReport,
    InventoryStats,
)
from .service import InventoryManagementService
from .config import InventoryManagementConfig

__all__ = [
    "app",
    "InventoryItem",
    "InventoryItemCreate",
    "InventoryItemUpdate",
    "InventoryAdjustment",
    "InventoryReservation",
    "InventoryRelease",
    "ReplenishmentRecommendation",
    "DiscrepancyReport",
    "InventoryStats",
    "InventoryManagementService",
    "InventoryManagementConfig",
]
