"""
Main application for the Warehouse Operations Agent.

This FastAPI application exposes the Warehouse Operations Agent API.
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

from .config import WarehouseOpsConfig, get_default_config, settings
from .schemas import (
    DockSchedule,
    DockScheduleCreate,
    DockScheduleListResponse,
    LaborForecastRequest,
    LaborForecastResponse,
    TaskOptimizationRequest,
    TaskOptimizationResponse,
    WarehouseTask,
    WarehouseTaskCreate,
    WarehouseTaskListResponse,
    WarehouseTaskStatus,
    WarehouseTaskType,
    WarehouseTaskUpdate,
    WarehouseTaskPriority,
)
from .service import WarehouseOpsService

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
    
    logger.info("Warehouse Operations Agent started")
    yield
    logger.info("Warehouse Operations Agent shutting down")


app = FastAPI(
    title="Warehouse Operations Agent",
    description="Lanework Warehouse Operations Agent API",
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
) -> WarehouseOpsService:
    """Get the WarehouseOpsService instance."""
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
    service = WarehouseOpsService(
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
# Warehouse Task Endpoints
# ============================================================================

@app.post(
    "/warehouse/tasks",
    response_model=WarehouseTask,
    summary="Create a warehouse task",
    description="Create a new warehouse task"
)
async def create_task(
    task_data: WarehouseTaskCreate,
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> WarehouseTask:
    """Create a new warehouse task."""
    task, agent_task = await service.create_task(
        task_data=task_data,
        tenant_id=x_tenant_id
    )
    
    # If approval is required, return the task but the client should check for pending approvals
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Warehouse task {task.id} created, pending approval")
    
    return task


@app.get(
    "/warehouse/tasks/{task_id}",
    response_model=WarehouseTask,
    summary="Get a warehouse task",
    description="Get a single warehouse task by ID"
)
async def get_task(
    task_id: str,
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> WarehouseTask:
    """Get a warehouse task by ID."""
    task = await service.get_task(task_id, x_tenant_id)
    
    if not task:
        raise NotFoundException("warehouse_task", task_id)
    
    return task


@app.get(
    "/warehouse/tasks",
    response_model=WarehouseTaskListResponse,
    summary="List warehouse tasks",
    description="List all warehouse tasks with optional filters"
)
async def list_tasks(
    warehouse_id: Optional[str] = Query(default=None),
    status: Optional[WarehouseTaskStatus] = Query(default=None),
    task_type: Optional[WarehouseTaskType] = Query(default=None),
    priority: Optional[WarehouseTaskPriority] = Query(default=None),
    assigned_to: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> WarehouseTaskListResponse:
    """List warehouse tasks."""
    tasks, total = await service.list_tasks(
        tenant_id=x_tenant_id,
        warehouse_id=warehouse_id,
        status=status,
        task_type=task_type,
        priority=priority,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset
    )
    
    return WarehouseTaskListResponse(
        tasks=tasks,
        total=total,
        limit=limit,
        offset=offset
    )


@app.patch(
    "/warehouse/tasks/{task_id}",
    response_model=WarehouseTask,
    summary="Update a warehouse task",
    description="Update warehouse task fields"
)
async def update_task(
    task_id: str,
    task_data: WarehouseTaskUpdate,
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> WarehouseTask:
    """Update a warehouse task."""
    task, agent_task = await service.update_task(
        task_id=task_id,
        task_data=task_data,
        tenant_id=x_tenant_id
    )
    
    if not task:
        raise NotFoundException("warehouse_task", task_id)
    
    return task


@app.delete(
    "/warehouse/tasks/{task_id}",
    status_code=204,
    summary="Delete a warehouse task",
    description="Delete a warehouse task"
)
async def delete_task(
    task_id: str,
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Delete a warehouse task."""
    success = await service.delete_task(task_id, x_tenant_id)
    
    if not success:
        raise NotFoundException("warehouse_task", task_id)


# ============================================================================
# Task Optimization Endpoints
# ============================================================================

@app.post(
    "/warehouse/tasks/optimize",
    response_model=TaskOptimizationResponse,
    summary="Optimize task sequencing",
    description="Optimize task sequencing for a warehouse"
)
async def optimize_tasks(
    request: TaskOptimizationRequest,
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> TaskOptimizationResponse:
    """Optimize task sequencing."""
    response, agent_task = await service.optimize_tasks(
        request=request,
        tenant_id=x_tenant_id
    )
    
    # If approval is required
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Task optimization pending approval: {agent_task.id}")
    
    return response


# ============================================================================
# Dock Schedule Endpoints
# ============================================================================

@app.get(
    "/warehouse/dock-schedule",
    response_model=DockScheduleListResponse,
    summary="Get dock schedules",
    description="Get dock schedules with optional filters"
)
async def get_dock_schedule(
    warehouse_id: Optional[str] = Query(default=None),
    date: Optional[date] = Query(default=None),
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> DockScheduleListResponse:
    """Get dock schedules."""
    return await service.get_dock_schedule(
        warehouse_id=warehouse_id,
        date=date,
        tenant_id=x_tenant_id
    )


@app.post(
    "/warehouse/dock-schedule",
    response_model=DockSchedule,
    summary="Create a dock schedule",
    description="Create a new dock schedule"
)
async def create_dock_schedule(
    schedule_data: DockScheduleCreate,
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> DockSchedule:
    """Create a dock schedule."""
    schedule, agent_task = await service.create_dock_schedule(
        schedule_data=schedule_data,
        tenant_id=x_tenant_id
    )
    
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Dock schedule {schedule.id} created, pending approval")
    
    return schedule


# ============================================================================
# Labor Forecast Endpoints
# ============================================================================

@app.post(
    "/warehouse/labor-forecast",
    response_model=LaborForecastResponse,
    summary="Generate labor forecast",
    description="Generate labor forecast for a warehouse"
)
async def generate_labor_forecast(
    request: LaborForecastRequest,
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> LaborForecastResponse:
    """Generate labor forecast."""
    response, agent_task = await service.generate_labor_forecast(
        request=request,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get(
    "/config",
    response_model=WarehouseOpsConfig,
    summary="Get configuration",
    description="Get the current agent configuration"
)
async def get_config(
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> WarehouseOpsConfig:
    """Get the current configuration."""
    return await service.get_config(x_tenant_id)


@app.patch(
    "/config",
    response_model=WarehouseOpsConfig,
    summary="Update configuration",
    description="Update the agent configuration"
)
async def update_config(
    config_updates: Dict[str, Any],
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> WarehouseOpsConfig:
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
        "agent": "warehouse-ops",
        "version": "1.0.0"
    }


@app.get(
    "/stats",
    summary="Get statistics",
    description="Get warehouse operations statistics"
)
async def get_stats(
    service: WarehouseOpsService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Dict[str, Any]:
    """Get warehouse operations statistics."""
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
