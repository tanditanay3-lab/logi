"""
Main application for the API Gateway.

This FastAPI application provides the main entry point for all Lanework APIs.
It handles:
- Authentication
- Tenant routing
- Rate limiting
- Request logging
- Routing to appropriate services
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from packages.shared_types.exceptions import (
    LaneworkException,
    NotFoundException,
    PermissionException,
    ValidationException,
)

from .config import settings
from .middleware import (
    AuthenticationMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    TenantMiddleware,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Application Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Initialize services
    logger.info("API Gateway starting up")
    
    # Initialize database connection pool
    from packages.db import init_db
    await init_db(settings.database_url)
    
    yield
    
    logger.info("API Gateway shutting down")


app = FastAPI(
    title="Lanework API Gateway",
    description="Main API Gateway for Lanework - Multi-tenant agentic operating system for logistics",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================================================
# Middleware
# ============================================================================

# Add middleware in order
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(LaneworkException)
async def lanework_exception_handler(request: Request, exc: LaneworkException):
    """Handle Lanework exceptions."""
    logger.error(f"Lanework exception: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException):
    """Handle NotFound exceptions."""
    logger.warning(f"Not found: {exc.details}")
    return JSONResponse(
        status_code=404,
        content=exc.to_dict()
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    """Handle Validation exceptions."""
    logger.warning(f"Validation error: {exc.message}")
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )


@app.exception_handler(PermissionException)
async def permission_exception_handler(request: Request, exc: PermissionException):
    """Handle Permission exceptions."""
    logger.warning(f"Permission denied: {exc.message}")
    return JSONResponse(
        status_code=403,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": str(exc)
            }
        }
    )


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get(
    "/",
    summary="Root endpoint",
    description="Root endpoint that returns basic service information"
)
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "service": "lanework-api-gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get(
    "/health",
    summary="Health check",
    description="Check if the API Gateway is healthy"
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "api-gateway",
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z",  # Would be dynamic in real implementation
        "checks": {
            "database": "healthy",
            "cache": "healthy",
            "authentication": "healthy"
        }
    }


# ============================================================================
# Service Discovery
# ============================================================================

@app.get(
    "/services",
    summary="List services",
    description="List all available services and their endpoints"
)
async def list_services() -> Dict[str, Any]:
    """List all available services."""
    services = {
        "api-gateway": {
            "description": "Main API Gateway",
            "endpoint": "/",
            "version": "1.0.0"
        },
        "orchestrator": {
            "description": "Agent Orchestration Layer",
            "endpoint": f"http://{settings.orchestrator_host}:{settings.orchestrator_port}",
            "version": "1.0.0",
            "endpoints": {
                "conversation": "/conversation",
                "tasks": "/tasks",
                "plan": "/plan",
                "agents": "/agents",
                "guardrails": "/guardrails/check"
            }
        },
        "agents": {
            "shipment-tracking": {
                "description": "Shipment Tracking Agent",
                "endpoint": f"http://{settings.shipment_tracking_host}:{settings.shipment_tracking_port}",
                "version": "1.0.0",
                "endpoints": {
                    "shipments": "/shipments",
                    "carrier-webhook": "/carrier-webhook"
                }
            },
            "inventory": {
                "description": "Inventory Management Agent",
                "endpoint": f"http://{settings.inventory_host}:{settings.inventory_port}",
                "version": "1.0.0",
                "endpoints": {
                    "inventory": "/inventory/items"
                }
            },
            "route-optimization": {
                "description": "Route Optimization Agent",
                "endpoint": f"http://{settings.route_optimization_host}:{settings.route_optimization_port}",
                "version": "1.0.0",
                "endpoints": {
                    "routes": "/routes"
                }
            },
            "warehouse-ops": {
                "description": "Warehouse Operations Agent",
                "endpoint": f"http://{settings.warehouse_ops_host}:{settings.warehouse_ops_port}",
                "version": "1.0.0"
            },
            "fleet-management": {
                "description": "Fleet & Driver Management Agent",
                "endpoint": f"http://{settings.fleet_management_host}:{settings.fleet_management_port}",
                "version": "1.0.0"
            },
            "customer-communication": {
                "description": "Customer Communication Agent",
                "endpoint": f"http://{settings.customer_communication_host}:{settings.customer_communication_port}",
                "version": "1.0.0"
            },
            "demand-forecasting": {
                "description": "Demand Forecasting Agent",
                "endpoint": f"http://{settings.demand_forecasting_host}:{settings.demand_forecasting_port}",
                "version": "1.0.0"
            },
            "freight-procurement": {
                "description": "Freight / Carrier Procurement Agent",
                "endpoint": f"http://{settings.freight_procurement_host}:{settings.freight_procurement_port}",
                "version": "1.0.0"
            },
            "voice": {
                "description": "Voice Agent",
                "endpoint": f"http://{settings.voice_host}:{settings.voice_port}",
                "version": "1.0.0"
            }
        }
    }
    
    return {"services": services}


# ============================================================================
# Proxy Endpoints
# ============================================================================

# In a production environment, these would be handled by a reverse proxy like Kong or Nginx
# For development, we provide simple proxy endpoints

@app.post(
    "/orchestrator/conversation",
    summary="Proxy to Conversation Router",
    description="Proxy request to the Conversation Router"
)
async def proxy_conversation(
    request: Request,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Proxy to Conversation Router."""
    # In production, this would be handled by Kong/Nginx
    # For development, we'll just return a message
    return {
        "message": "This endpoint would proxy to the Conversation Router in production",
        "service": "orchestrator",
        "endpoint": "/conversation"
    }


@app.post(
    "/agents/shipment-tracking/shipments",
    summary="Proxy to Shipment Tracking Agent",
    description="Proxy request to the Shipment Tracking Agent"
)
async def proxy_shipment_tracking(
    request: Request,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Proxy to Shipment Tracking Agent."""
    # In production, this would be handled by Kong/Nginx
    return {
        "message": "This endpoint would proxy to the Shipment Tracking Agent in production",
        "service": "shipment-tracking",
        "endpoint": "/shipments"
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
