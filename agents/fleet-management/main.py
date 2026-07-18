"""
Main application for the Fleet & Driver Management Agent.

This FastAPI application exposes the Fleet & Driver Management Agent API.
"""

import logging
from contextlib import asynccontextmanager
from datetime import date
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

from .config import FleetManagementConfig, get_default_config, settings
from .schemas import (
    ComplianceAlertListResponse,
    Driver,
    DriverCreate,
    DriverListResponse,
    DriverStatus,
    DriverUpdate,
    DriverVehicleAssignment,
    DriverVehicleAssignmentResponse,
    FleetStats,
    HOSComplianceCheckRequest,
    HOSComplianceCheckResponse,
    HOSEventCreate,
    HOSStatus,
    MaintenanceRecord,
    MaintenanceRecordCreate,
    Vehicle,
    VehicleCreate,
    VehicleListResponse,
    VehicleStatus,
    VehicleType,
)
from .service import FleetManagementService

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
    
    logger.info("Fleet & Driver Management Agent started")
    yield
    logger.info("Fleet & Driver Management Agent shutting down")


app = FastAPI(
    title="Fleet & Driver Management Agent",
    description="Lanework Fleet & Driver Management Agent API",
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
) -> FleetManagementService:
    """Get the FleetManagementService instance."""
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
    service = FleetManagementService(
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
# Driver Endpoints
# ============================================================================

@app.post(
    "/fleet/drivers",
    response_model=Driver,
    summary="Create a driver",
    description="Create a new driver"
)
async def create_driver(
    driver_data: DriverCreate,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Driver:
    """Create a new driver."""
    driver, agent_task = await service.create_driver(
        driver_data=driver_data,
        tenant_id=x_tenant_id
    )
    
    return driver


@app.get(
    "/fleet/drivers/{driver_id}",
    response_model=Driver,
    summary="Get a driver",
    description="Get a single driver by ID"
)
async def get_driver(
    driver_id: str,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Driver:
    """Get a driver by ID."""
    driver = await service.get_driver(driver_id, x_tenant_id)
    
    if not driver:
        raise NotFoundException("driver", driver_id)
    
    return driver


@app.get(
    "/fleet/drivers",
    response_model=DriverListResponse,
    summary="List drivers",
    description="List all drivers with optional filters"
)
async def list_drivers(
    status: Optional[DriverStatus] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> DriverListResponse:
    """List drivers."""
    drivers, total = await service.list_drivers(
        tenant_id=x_tenant_id,
        status=status,
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset
    )
    
    return DriverListResponse(
        drivers=drivers,
        total=total,
        limit=limit,
        offset=offset
    )


@app.patch(
    "/fleet/drivers/{driver_id}",
    response_model=Driver,
    summary="Update a driver",
    description="Update driver fields"
)
async def update_driver(
    driver_id: str,
    driver_data: DriverUpdate,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Driver:
    """Update a driver."""
    driver, agent_task = await service.update_driver(
        driver_id=driver_id,
        driver_data=driver_data,
        tenant_id=x_tenant_id
    )
    
    if not driver:
        raise NotFoundException("driver", driver_id)
    
    return driver


@app.delete(
    "/fleet/drivers/{driver_id}",
    status_code=204,
    summary="Delete a driver",
    description="Delete a driver"
)
async def delete_driver(
    driver_id: str,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Delete a driver."""
    success = await service.delete_driver(driver_id, x_tenant_id)
    
    if not success:
        raise NotFoundException("driver", driver_id)


# ============================================================================
# HOS Endpoints
# ============================================================================

@app.post(
    "/fleet/drivers/{driver_id}/hos-update",
    response_model=HOSStatus,
    summary="Update HOS status",
    description="Update HOS status for a driver"
)
async def update_hos_status(
    driver_id: str,
    event_data: HOSEventCreate,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> HOSStatus:
    """Update HOS status for a driver."""
    hos_status, agent_task = await service.update_hos_status(
        driver_id=driver_id,
        event_data=event_data,
        tenant_id=x_tenant_id
    )
    
    return hos_status


# ============================================================================
# Vehicle Endpoints
# ============================================================================

@app.post(
    "/fleet/vehicles",
    response_model=Vehicle,
    summary="Create a vehicle",
    description="Create a new vehicle"
)
async def create_vehicle(
    vehicle_data: VehicleCreate,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Vehicle:
    """Create a new vehicle."""
    vehicle, agent_task = await service.create_vehicle(
        vehicle_data=vehicle_data,
        tenant_id=x_tenant_id
    )
    
    return vehicle


@app.get(
    "/fleet/vehicles/{vehicle_id}",
    response_model=Vehicle,
    summary="Get a vehicle",
    description="Get a single vehicle by ID"
)
async def get_vehicle(
    vehicle_id: str,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Vehicle:
    """Get a vehicle by ID."""
    vehicle = await service.get_vehicle(vehicle_id, x_tenant_id)
    
    if not vehicle:
        raise NotFoundException("vehicle", vehicle_id)
    
    return vehicle


@app.get(
    "/fleet/vehicles",
    response_model=VehicleListResponse,
    summary="List vehicles",
    description="List all vehicles with optional filters"
)
async def list_vehicles(
    status: Optional[VehicleStatus] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> VehicleListResponse:
    """List vehicles."""
    vehicles, total = await service.list_vehicles(
        tenant_id=x_tenant_id,
        status=status,
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset
    )
    
    return VehicleListResponse(
        vehicles=vehicles,
        total=total,
        limit=limit,
        offset=offset
    )


@app.patch(
    "/fleet/vehicles/{vehicle_id}",
    response_model=Vehicle,
    summary="Update a vehicle",
    description="Update vehicle fields"
)
async def update_vehicle(
    vehicle_id: str,
    vehicle_data: VehicleUpdate,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Vehicle:
    """Update a vehicle."""
    vehicle, agent_task = await service.update_vehicle(
        vehicle_id=vehicle_id,
        vehicle_data=vehicle_data,
        tenant_id=x_tenant_id
    )
    
    if not vehicle:
        raise NotFoundException("vehicle", vehicle_id)
    
    return vehicle


@app.delete(
    "/fleet/vehicles/{vehicle_id}",
    status_code=204,
    summary="Delete a vehicle",
    description="Delete a vehicle"
)
async def delete_vehicle(
    vehicle_id: str,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Delete a vehicle."""
    success = await service.delete_vehicle(vehicle_id, x_tenant_id)
    
    if not success:
        raise NotFoundException("vehicle", vehicle_id)


# ============================================================================
# Maintenance Endpoints
# ============================================================================

@app.post(
    "/fleet/vehicles/{vehicle_id}/maintenance",
    response_model=MaintenanceRecord,
    summary="Log maintenance",
    description="Log a maintenance event for a vehicle"
)
async def log_maintenance(
    vehicle_id: str,
    maintenance_data: MaintenanceRecordCreate,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> MaintenanceRecord:
    """Log maintenance for a vehicle."""
    maintenance, agent_task = await service.log_maintenance(
        vehicle_id=vehicle_id,
        maintenance_data=maintenance_data,
        tenant_id=x_tenant_id
    )
    
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Maintenance log pending approval: {agent_task.id}")
    
    return maintenance


# ============================================================================
# HOS Compliance Check Endpoint
# ============================================================================

@app.post(
    "/fleet/drivers/{driver_id}/check-hos",
    response_model=HOSComplianceCheckResponse,
    summary="Check HOS compliance",
    description="Check HOS compliance for a potential route assignment"
)
async def check_hos_compliance(
    driver_id: str,
    request: HOSComplianceCheckRequest,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> HOSComplianceCheckResponse:
    """Check HOS compliance for a driver."""
    response, agent_task = await service.check_hos_compliance(
        driver_id=driver_id,
        request=request,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Driver-Vehicle Assignment Endpoint
# ============================================================================

@app.post(
    "/fleet/drivers/{driver_id}/assign-vehicle",
    response_model=DriverVehicleAssignmentResponse,
    summary="Assign driver to vehicle",
    description="Assign a driver to a vehicle"
)
async def assign_driver_to_vehicle(
    driver_id: str,
    assignment: DriverVehicleAssignment,
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> DriverVehicleAssignmentResponse:
    """Assign a driver to a vehicle."""
    response, agent_task = await service.assign_driver_to_vehicle(
        driver_id=driver_id,
        assignment=assignment,
        tenant_id=x_tenant_id
    )
    
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Driver-vehicle assignment pending approval: {agent_task.id}")
    
    return response


# ============================================================================
# Compliance Alerts Endpoint
# ============================================================================

@app.get(
    "/fleet/alerts",
    response_model=ComplianceAlertListResponse,
    summary="Get compliance alerts",
    description="Get all compliance alerts"
)
async def get_compliance_alerts(
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ComplianceAlertListResponse:
    """Get compliance alerts."""
    return await service.get_compliance_alerts(x_tenant_id)


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get(
    "/config",
    response_model=FleetManagementConfig,
    summary="Get configuration",
    description="Get the current agent configuration"
)
async def get_config(
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> FleetManagementConfig:
    """Get the current configuration."""
    return await service.get_config(x_tenant_id)


@app.patch(
    "/config",
    response_model=FleetManagementConfig,
    summary="Update configuration",
    description="Update the agent configuration"
)
async def update_config(
    config_updates: Dict[str, Any],
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> FleetManagementConfig:
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
        "agent": "fleet-management",
        "version": "1.0.0"
    }


@app.get(
    "/stats",
    summary="Get statistics",
    description="Get fleet management statistics"
)
async def get_stats(
    service: FleetManagementService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Dict[str, Any]:
    """Get fleet management statistics."""
    return await service.get_stats(x_tenant_id)


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
