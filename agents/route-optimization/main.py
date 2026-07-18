"""
Main application for the Route Optimization Agent.

This FastAPI application exposes the Route Optimization Agent API.
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

from .config import RouteOptimizationConfig, get_default_config, settings
from .schemas import (
    DriverInfo,
    Location,
    OptimizedRoute,
    ReoptimizationTrigger,
    Route,
    RouteAssignment,
    RouteAssignmentResponse,
    RouteConstraints,
    RouteCreate,
    RouteListResponse,
    RouteMetrics,
    RouteOptimizationRequest,
    RouteOptimizationResponse,
    RouteReoptimizationRequest,
    RouteReoptimizationResponse,
    RouteStats,
    RouteStatus,
    RouteStop,
    RouteStopCreate,
    RouteStopStatus,
    RouteStopType,
    RouteStopUpdate,
    RouteUpdate,
    StopActionRequest,
    StopActionResponse,
    VehicleInfo,
)
from .service import RouteOptimizationService

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
    
    logger.info("Route Optimization Agent started")
    yield
    logger.info("Route Optimization Agent shutting down")


app = FastAPI(
    title="Route Optimization Agent",
    description="Lanework Route Optimization Agent API",
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
) -> RouteOptimizationService:
    """Get the RouteOptimizationService instance."""
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
    service = RouteOptimizationService(
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
# Route Endpoints
# ============================================================================

@app.post(
    "/routes",
    response_model=Route,
    summary="Create a route",
    description="Create a new route"
)
async def create_route(
    route_data: RouteCreate,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Route:
    """Create a new route."""
    route, agent_task = await service.create_route(
        route_data=route_data,
        tenant_id=x_tenant_id
    )
    
    # If approval is required, return the route but the client should check for pending approvals
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Route {route.id} created, pending approval")
    
    return route


@app.get(
    "/routes/{route_id}",
    response_model=Route,
    summary="Get a route",
    description="Get a single route by ID"
)
async def get_route(
    route_id: str,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Route:
    """Get a route by ID."""
    route = await service.get_route(route_id, x_tenant_id)
    
    if not route:
        raise NotFoundException("route", route_id)
    
    return route


@app.get(
    "/routes",
    response_model=RouteListResponse,
    summary="List routes",
    description="List all routes with optional filters"
)
async def list_routes(
    status: Optional[RouteStatus] = Query(default=None),
    driver_id: Optional[str] = Query(default=None),
    vehicle_id: Optional[str] = Query(default=None),
    date: Optional[date] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> RouteListResponse:
    """List routes."""
    routes, total = await service.list_routes(
        tenant_id=x_tenant_id,
        status=status,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        date=date,
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset
    )
    
    return RouteListResponse(
        routes=routes,
        total=total,
        limit=limit,
        offset=offset
    )


@app.patch(
    "/routes/{route_id}",
    response_model=Route,
    summary="Update a route",
    description="Update route fields"
)
async def update_route(
    route_id: str,
    route_data: RouteUpdate,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Route:
    """Update a route."""
    route, agent_task = await service.update_route(
        route_id=route_id,
        route_data=route_data,
        tenant_id=x_tenant_id
    )
    
    if not route:
        raise NotFoundException("route", route_id)
    
    return route


@app.delete(
    "/routes/{route_id}",
    status_code=204,
    summary="Delete a route",
    description="Delete a route"
)
async def delete_route(
    route_id: str,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Delete a route."""
    success = await service.delete_route(route_id, x_tenant_id)
    
    if not success:
        raise NotFoundException("route", route_id)


# ============================================================================
# Route Optimization Endpoints
# ============================================================================

@app.post(
    "/routes/optimize",
    response_model=RouteOptimizationResponse,
    summary="Optimize routes",
    description="Generate optimized routes from a set of stops"
)
async def optimize_routes(
    request: RouteOptimizationRequest,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> RouteOptimizationResponse:
    """Generate optimized routes from a set of stops."""
    response = await service.optimize_routes(
        request=request,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Route Re-optimization Endpoints
# ============================================================================

@app.post(
    "/routes/{route_id}/reoptimize",
    response_model=RouteReoptimizationResponse,
    summary="Re-optimize a route",
    description="Re-optimize an existing route"
)
async def reoptimize_route(
    route_id: str,
    request: RouteReoptimizationRequest,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> RouteReoptimizationResponse:
    """Re-optimize an existing route."""
    response = await service.reoptimize_route(
        route_id=route_id,
        request=request,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Route Assignment Endpoints
# ============================================================================

@app.post(
    "/routes/{route_id}/assign",
    response_model=RouteAssignmentResponse,
    summary="Assign route to driver",
    description="Assign a route to a driver and vehicle"
)
async def assign_route(
    route_id: str,
    assignment_data: RouteAssignment,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> RouteAssignmentResponse:
    """Assign a route to a driver and vehicle."""
    response = await service.assign_route(
        route_id=route_id,
        assignment_data=assignment_data,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Route Status Endpoints
# ============================================================================

@app.post(
    "/routes/{route_id}/start",
    response_model=Route,
    summary="Start a route",
    description="Mark a route as started"
)
async def start_route(
    route_id: str,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Route:
    """Mark a route as started."""
    route = await service.start_route(route_id, x_tenant_id)
    
    if not route:
        raise NotFoundException("route", route_id)
    
    return route


@app.post(
    "/routes/{route_id}/complete",
    response_model=Route,
    summary="Complete a route",
    description="Mark a route as completed"
)
async def complete_route(
    route_id: str,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Route:
    """Mark a route as completed."""
    route = await service.complete_route(route_id, x_tenant_id)
    
    if not route:
        raise NotFoundException("route", route_id)
    
    return route


# ============================================================================
# Stop Endpoints
# ============================================================================

@app.patch(
    "/routes/{route_id}/stops/{stop_id}",
    response_model=Route,
    summary="Update a stop",
    description="Update a route stop"
)
async def update_stop(
    route_id: str,
    stop_id: str,
    stop_data: RouteStopUpdate,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Route:
    """Update a route stop."""
    route = await service.update_stop(
        route_id=route_id,
        stop_id=stop_id,
        stop_data=stop_data,
        tenant_id=x_tenant_id
    )
    
    if not route:
        raise NotFoundException("stop", stop_id)
    
    return route


@app.post(
    "/routes/{route_id}/stops/{stop_id}/start",
    response_model=StopActionResponse,
    summary="Start a stop",
    description="Mark a stop as started"
)
async def start_stop(
    route_id: str,
    stop_id: str,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> StopActionResponse:
    """Mark a stop as started."""
    response = await service.start_stop(
        route_id=route_id,
        stop_id=stop_id,
        tenant_id=x_tenant_id
    )
    
    return response


@app.post(
    "/routes/{route_id}/stops/{stop_id}/complete",
    response_model=StopActionResponse,
    summary="Complete a stop",
    description="Mark a stop as completed"
)
async def complete_stop(
    route_id: str,
    stop_id: str,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> StopActionResponse:
    """Mark a stop as completed."""
    response = await service.complete_stop(
        route_id=route_id,
        stop_id=stop_id,
        tenant_id=x_tenant_id
    )
    
    return response


@app.post(
    "/routes/{route_id}/stops/{stop_id}/skip",
    response_model=StopActionResponse,
    summary="Skip a stop",
    description="Skip a stop"
)
async def skip_stop(
    route_id: str,
    stop_id: str,
    request: StopActionRequest,
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> StopActionResponse:
    """Skip a stop."""
    response = await service.skip_stop(
        route_id=route_id,
        stop_id=stop_id,
        request=request,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.get(
    "/routes/stats",
    response_model=RouteStats,
    summary="Get route statistics",
    description="Get route statistics for a tenant"
)
async def get_stats(
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> RouteStats:
    """Get route statistics."""
    return await service.get_stats(x_tenant_id)


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get(
    "/config",
    response_model=RouteOptimizationConfig,
    summary="Get configuration",
    description="Get the current agent configuration"
)
async def get_config(
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> RouteOptimizationConfig:
    """Get the current configuration."""
    return await service.get_config(x_tenant_id)


@app.patch(
    "/config",
    response_model=RouteOptimizationConfig,
    summary="Update configuration",
    description="Update the agent configuration"
)
async def update_config(
    config_updates: Dict[str, Any],
    service: RouteOptimizationService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> RouteOptimizationConfig:
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
        "agent": "route-optimization",
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
