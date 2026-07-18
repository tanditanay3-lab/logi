"""
Main application for the Inventory Management Agent.

This FastAPI application exposes the Inventory Management Agent API.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db import get_db_session
from packages.shared_types.exceptions import (
    LaneworkException,
    NotFoundException,
    PermissionException,
    ValidationException,
)

from .config import InventoryManagementConfig, get_default_config, settings
from .schemas import (
    AdjustmentType,
    DiscrepancyReport,
    DiscrepancyResponse,
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryAdjustment,
    InventoryListResponse,
    InventoryReservation,
    InventoryRelease,
    InventoryStats,
    InventoryPriority,
    MovementHistoryResponse,
    ReplenishmentRecommendation,
    ReplenishmentRequest,
)
from .service import InventoryManagementService

logger = logging.getLogger(__name__)


# ============================================================================
# Application Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Initialize database
    from packages.db import init_db
    await init_db(settings.database_url)
    
    logger.info("Inventory Management Agent started")
    yield
    logger.info("Inventory Management Agent shutting down")


app = FastAPI(
    title="Inventory Management Agent",
    description="Lanework Inventory Management Agent API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================================================
# Dependencies
# ============================================================================

async def get_service(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> InventoryManagementService:
    """Get the InventoryManagementService instance."""
    # Extract tenant ID
    tenant_id = x_tenant_id or settings.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    
    # Verify API key if configured
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]  # Remove "Bearer " prefix
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Create service with tenant-specific config
    config = get_default_config()
    
    # Initialize service
    service = InventoryManagementService(
        db_session=db_session,
        config=config
    )
    
    await service.initialize()
    
    # Store service in request state for cleanup
    request.state.service = service
    
    return service


async def cleanup_service(request: Request):
    """Cleanup service after request."""
    if hasattr(request.state, 'service'):
        await request.state.service.close()


app.middleware("http")(cleanup_service)


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(LaneworkException)
async def lanework_exception_handler(request: Request, exc: LaneworkException):
    """Handle Lanework exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException):
    """Handle NotFound exceptions."""
    return JSONResponse(
        status_code=404,
        content=exc.to_dict()
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    """Handle Validation exceptions."""
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )


@app.exception_handler(PermissionException)
async def permission_exception_handler(request: Request, exc: PermissionException):
    """Handle Permission exceptions."""
    return JSONResponse(
        status_code=403,
        content=exc.to_dict()
    )


# ============================================================================
# Inventory Item Endpoints
# ============================================================================

@app.post(
    "/inventory/items",
    response_model=InventoryItem,
    summary="Create inventory item",
    description="Create a new inventory item"
)
async def create_inventory_item(
    item_data: InventoryItemCreate,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryItem:
    """Create a new inventory item."""
    item, agent_task = await service.create_inventory_item(
        item_data=item_data,
        tenant_id=x_tenant_id
    )
    
    # If approval is required, return the item but the client should check for pending approvals
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Inventory item {item.id} created, pending approval")
    
    return item


@app.get(
    "/inventory/items/{item_id}",
    response_model=InventoryItem,
    summary="Get inventory item",
    description="Get a single inventory item by ID"
)
async def get_inventory_item(
    item_id: str,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryItem:
    """Get an inventory item by ID."""
    item = await service.get_inventory_item(item_id, x_tenant_id)
    
    if not item:
        raise NotFoundException("inventory_item", item_id)
    
    return item


@app.get(
    "/inventory/items",
    response_model=InventoryListResponse,
    summary="List inventory items",
    description="List all inventory items with optional filters"
)
async def list_inventory_items(
    warehouse_id: Optional[str] = Query(default=None),
    sku: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    low_stock: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryListResponse:
    """List inventory items."""
    items, total = await service.list_inventory_items(
        tenant_id=x_tenant_id,
        warehouse_id=warehouse_id,
        sku=sku,
        category=category,
        low_stock=low_stock,
        limit=limit,
        offset=offset
    )
    
    return InventoryListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset
    )


@app.patch(
    "/inventory/items/{item_id}",
    response_model=InventoryItem,
    summary="Update inventory item",
    description="Update inventory item fields"
)
async def update_inventory_item(
    item_id: str,
    item_data: InventoryItemUpdate,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryItem:
    """Update an inventory item."""
    item, agent_task = await service.update_inventory_item(
        item_id=item_id,
        item_data=item_data,
        tenant_id=x_tenant_id
    )
    
    if not item:
        raise NotFoundException("inventory_item", item_id)
    
    return item


@app.delete(
    "/inventory/items/{item_id}",
    status_code=204,
    summary="Delete inventory item",
    description="Delete an inventory item"
)
async def delete_inventory_item(
    item_id: str,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Delete an inventory item."""
    success = await service.delete_inventory_item(item_id, x_tenant_id)
    
    if not success:
        raise NotFoundException("inventory_item", item_id)


# ============================================================================
# Inventory Adjustment Endpoints
# ============================================================================

@app.post(
    "/inventory/items/{item_id}/adjust",
    response_model=InventoryItem,
    summary="Adjust inventory quantity",
    description="Adjust inventory quantity with various adjustment types"
)
async def adjust_inventory(
    item_id: str,
    adjustment_data: InventoryAdjustment,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryItem:
    """Adjust inventory quantity."""
    item, agent_task = await service.adjust_inventory(
        item_id=item_id,
        adjustment_data=adjustment_data,
        tenant_id=x_tenant_id
    )
    
    if not item:
        raise NotFoundException("inventory_item", item_id)
    
    # If approval is required, the client should check for pending approvals
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Inventory adjustment for {item_id} pending approval")
    
    return item


# ============================================================================
# Inventory Reservation Endpoints
# ============================================================================

@app.post(
    "/inventory/items/{item_id}/reserve",
    response_model=InventoryItem,
    summary="Reserve inventory",
    description="Reserve inventory for an order"
)
async def reserve_inventory(
    item_id: str,
    reservation_data: InventoryReservation,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryItem:
    """Reserve inventory for an order."""
    item, agent_task = await service.reserve_inventory(
        item_id=item_id,
        reservation_data=reservation_data,
        tenant_id=x_tenant_id
    )
    
    if not item:
        raise NotFoundException("inventory_item", item_id)
    
    # If approval is required, the client should check for pending approvals
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Inventory reservation for {item_id} pending approval")
    elif agent_task and agent_task.status == "failed":
        raise HTTPException(status_code=400, detail=agent_task.error_message or "Insufficient inventory")
    
    return item


@app.post(
    "/inventory/items/{item_id}/release",
    response_model=InventoryItem,
    summary="Release inventory",
    description="Release reserved inventory"
)
async def release_inventory(
    item_id: str,
    release_data: InventoryRelease,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryItem:
    """Release reserved inventory."""
    item, agent_task = await service.release_inventory(
        item_id=item_id,
        release_data=release_data,
        tenant_id=x_tenant_id
    )
    
    if not item:
        raise NotFoundException("inventory_item", item_id)
    
    # If approval is required, the client should check for pending approvals
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Inventory release for {item_id} pending approval")
    
    return item


# ============================================================================
# Replenishment Endpoints
# ============================================================================

@app.post(
    "/inventory/replenishment-recommendations",
    response_model=List[ReplenishmentRecommendation],
    summary="Get replenishment recommendations",
    description="Generate replenishment recommendations for inventory items"
)
async def get_replenishment_recommendations(
    request: ReplenishmentRequest,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> List[ReplenishmentRecommendation]:
    """Generate replenishment recommendations."""
    recommendations = await service.get_replenishment_recommendations(
        request=request,
        tenant_id=x_tenant_id
    )
    
    return recommendations


# ============================================================================
# Discrepancy Endpoints
# ============================================================================

@app.post(
    "/inventory/discrepancies",
    response_model=DiscrepancyResponse,
    summary="Report discrepancy",
    description="Report a stock discrepancy"
)
async def report_discrepancy(
    discrepancy_data: DiscrepancyReport,
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> DiscrepancyResponse:
    """Report a stock discrepancy."""
    response = await service.report_discrepancy(
        discrepancy_data=discrepancy_data,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Movement History Endpoints
# ============================================================================

@app.get(
    "/inventory/items/{item_id}/movements",
    response_model=MovementHistoryResponse,
    summary="Get movement history",
    description="Get the movement history for an inventory item"
)
async def get_movement_history(
    item_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> MovementHistoryResponse:
    """Get movement history for an inventory item."""
    response = await service.get_movement_history(
        item_id=item_id,
        tenant_id=x_tenant_id,
        limit=limit,
        offset=offset
    )
    
    return response


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.get(
    "/inventory/stats",
    response_model=InventoryStats,
    summary="Get inventory statistics",
    description="Get inventory statistics for a tenant"
)
async def get_stats(
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryStats:
    """Get inventory statistics."""
    return await service.get_stats(x_tenant_id)


# ============================================================================
# Low Stock Alerts Endpoint
# ============================================================================

@app.get(
    "/inventory/low-stock",
    response_model=List[LowStockAlert],
    summary="Get low stock alerts",
    description="Get all items that are currently low on stock"
)
async def get_low_stock_alerts(
    warehouse_id: Optional[str] = Query(default=None),
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> List[LowStockAlert]:
    """Get low stock alerts."""
    # Get all items that are low on stock
    items, _ = await service.list_inventory_items(
        tenant_id=x_tenant_id,
        warehouse_id=warehouse_id,
        low_stock=True,
        limit=1000
    )
    
    alerts = []
    for item in items:
        if item.reorder_point and item.quantity_on_hand <= item.reorder_point:
            alerts.append(LowStockAlert(
                item_id=item.id,
                sku=item.sku,
                name=item.name,
                current_quantity=item.quantity_on_hand,
                reorder_point=item.reorder_point,
                quantity_below=item.reorder_point - item.quantity_on_hand,
                warehouse_id=item.warehouse_id,
                location=item.location.to_string() if item.location else None
            ))
    
    return alerts


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get(
    "/config",
    response_model=InventoryManagementConfig,
    summary="Get configuration",
    description="Get the current agent configuration"
)
async def get_config(
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryManagementConfig:
    """Get the current configuration."""
    return await service.get_config(x_tenant_id)


@app.patch(
    "/config",
    response_model=InventoryManagementConfig,
    summary="Update configuration",
    description="Update the agent configuration"
)
async def update_config(
    config_updates: Dict[str, Any],
    service: InventoryManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> InventoryManagementConfig:
    """Update the configuration."""
    return await service.update_config(x_tenant_id, config_updates)


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get(
    "/health",
    summary="Health check",
    description="Check if the agent is healthy"
)
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "inventory-management",
        "version": "1.0.0"
    }


# ============================================================================
# Run the application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level="debug" if settings.api_debug else "info"
    )
