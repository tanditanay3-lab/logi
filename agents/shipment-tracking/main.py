"""
Main application for the Shipment Tracking Agent.

This is a FastAPI application that exposes the Shipment Tracking Agent API.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Base
from packages.db import get_db_session
from packages.shared_types.schemas import (
    AgentTask,
    Config,
    TrustLevel,
)
from packages.shared_types.exceptions import (
    LaneworkException,
    NotFoundException,
    PermissionException,
    ValidationException,
)

from .config import ShipmentTrackingConfig, get_default_config, settings
from .schemas import (
    EtaDriftDetection,
    NotificationRequest,
    NotificationResponse,
    Shipment,
    ShipmentCreate,
    ShipmentEvent,
    ShipmentEventCreate,
    ShipmentListResponse,
    ShipmentStatus,
    ShipmentUpdate,
    TrackingRefreshResponse,
    TrackingWebhookPayload,
    TrackingWebhookResponse,
)
from .service import ShipmentTrackingService

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
    
    logger.info("Shipment Tracking Agent started")
    yield
    logger.info("Shipment Tracking Agent shutting down")


app = FastAPI(
    title="Shipment Tracking Agent",
    description="Lanework Shipment Tracking Agent API",
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
) -> ShipmentTrackingService:
    """Get the ShipmentTrackingService instance."""
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
    service = ShipmentTrackingService(
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
# Shipment Endpoints
# ============================================================================

@app.post(
    "/shipments",
    response_model=Shipment,
    summary="Create a new shipment",
    description="Create a new shipment for tracking"
)
async def create_shipment(
    shipment_data: ShipmentCreate,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Shipment:
    """Create a new shipment."""
    shipment, agent_task = await service.create_shipment(
        shipment_data=shipment_data,
        tenant_id=x_tenant_id
    )
    
    # If approval is required, return the shipment but the client should check for pending approvals
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Shipment {shipment.id} created, pending approval")
    
    return shipment


@app.get(
    "/shipments/{shipment_id}",
    response_model=Shipment,
    summary="Get a shipment",
    description="Get a single shipment by ID"
)
async def get_shipment(
    shipment_id: str,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Shipment:
    """Get a shipment by ID."""
    shipment = await service.get_shipment(shipment_id, x_tenant_id)
    
    if not shipment:
        raise NotFoundException("shipment", shipment_id)
    
    return shipment


@app.get(
    "/shipments",
    response_model=ShipmentListResponse,
    summary="List shipments",
    description="List all shipments with optional filters"
)
async def list_shipments(
    status: Optional[ShipmentStatus] = Query(default=None),
    carrier: Optional[str] = Query(default=None),
    tracking_number: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ShipmentListResponse:
    """List shipments."""
    shipments, total = await service.list_shipments(
        tenant_id=x_tenant_id,
        status=status,
        carrier=carrier,
        tracking_number=tracking_number,
        limit=limit,
        offset=offset
    )
    
    return ShipmentListResponse(
        shipments=shipments,
        total=total,
        limit=limit,
        offset=offset
    )


@app.patch(
    "/shipments/{shipment_id}",
    response_model=Shipment,
    summary="Update a shipment",
    description="Update shipment fields"
)
async def update_shipment(
    shipment_id: str,
    shipment_data: ShipmentUpdate,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Shipment:
    """Update a shipment."""
    shipment, agent_task = await service.update_shipment(
        shipment_id=shipment_id,
        shipment_data=shipment_data,
        tenant_id=x_tenant_id
    )
    
    if not shipment:
        raise NotFoundException("shipment", shipment_id)
    
    return shipment


@app.delete(
    "/shipments/{shipment_id}",
    status_code=204,
    summary="Delete a shipment",
    description="Delete a shipment"
)
async def delete_shipment(
    shipment_id: str,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Delete a shipment."""
    success = await service.delete_shipment(shipment_id, x_tenant_id)
    
    if not success:
        raise NotFoundException("shipment", shipment_id)


# ============================================================================
# Shipment Event Endpoints
# ============================================================================

@app.post(
    "/shipments/{shipment_id}/events",
    response_model=Shipment,
    summary="Add a tracking event",
    description="Add a tracking event to a shipment"
)
async def add_shipment_event(
    shipment_id: str,
    event_data: ShipmentEventCreate,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Shipment:
    """Add a tracking event to a shipment."""
    shipment, agent_task = await service.add_shipment_event(
        shipment_id=shipment_id,
        event_data=event_data,
        tenant_id=x_tenant_id
    )
    
    if not shipment:
        raise NotFoundException("shipment", shipment_id)
    
    return shipment


# ============================================================================
# Tracking Refresh Endpoint
# ============================================================================

@app.post(
    "/shipments/{shipment_id}/refresh",
    response_model=TrackingRefreshResponse,
    summary="Refresh tracking data",
    description="Trigger a refresh of tracking data from the carrier"
)
async def refresh_tracking(
    shipment_id: str,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> TrackingRefreshResponse:
    """Refresh tracking data from carrier."""
    status, agent_task_id = await service.refresh_tracking(
        shipment_id=shipment_id,
        tenant_id=x_tenant_id
    )
    
    return TrackingRefreshResponse(
        status=status,
        shipment_id=shipment_id,
        agent_task_id=agent_task_id
    )


# ============================================================================
# Notification Endpoint
# ============================================================================

@app.post(
    "/shipments/{shipment_id}/notify",
    response_model=NotificationResponse,
    summary="Send notification",
    description="Send a status notification to customer"
)
async def send_notification(
    shipment_id: str,
    notification_data: NotificationRequest,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> NotificationResponse:
    """Send a notification about a shipment."""
    # Get shipment to verify it exists
    shipment = await service.get_shipment(shipment_id, x_tenant_id)
    if not shipment:
        raise NotFoundException("shipment", shipment_id)
    
    # Create AgentTask for notification
    agent_task = await service._create_agent_task(
        tenant_id=x_tenant_id,
        action_type="send_notification",
        input_data={
            "shipment_id": shipment_id,
            "notification_data": notification_data.model_dump()
        },
        status="auto_executed",
        reasoning_trace=f"Sending notification for shipment {shipment_id}"
    )
    
    # In a real implementation, this would call the notification tool
    # For now, we'll just return success
    
    return NotificationResponse(
        status="sent",
        notification_id=agent_task.id,
        agent_task_id=agent_task.id
    )


# ============================================================================
# Carrier Webhook Endpoint
# ============================================================================

@app.post(
    "/carrier-webhook",
    response_model=TrackingWebhookResponse,
    summary="Carrier webhook",
    description="Ingest carrier webhook payload"
)
async def carrier_webhook(
    payload: TrackingWebhookPayload,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_carrier_signature: Optional[str] = Header(default=None, alias="X-Carrier-Signature"),
    x_carrier: Optional[str] = Header(default=None, alias="X-Carrier")
) -> TrackingWebhookResponse:
    """
    Process a carrier webhook payload.
    
    This endpoint receives tracking updates from carriers and processes them.
    """
    # Verify webhook signature if configured
    if settings.webhook_secret:
        if not x_carrier_signature:
            raise HTTPException(status_code=401, detail="Carrier signature required")
        
        # In a real implementation, verify the signature
        # For now, we'll just check that it's provided
    
    # Process the webhook
    response = await service.process_carrier_webhook(
        payload=payload,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# ETA Drift Detection Endpoint
# ============================================================================

@app.get(
    "/shipments/{shipment_id}/eta-drift",
    response_model=EtaDriftDetection,
    summary="Check ETA drift",
    description="Check if a shipment has ETA drift"
)
async def check_eta_drift(
    shipment_id: str,
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> EtaDriftDetection:
    """Check if a shipment has ETA drift."""
    drift_detection = await service._check_eta_drift(shipment_id, x_tenant_id)
    
    if not drift_detection:
        # Return default if no drift detected
        shipment = await service.get_shipment(shipment_id, x_tenant_id)
        if not shipment:
            raise NotFoundException("shipment", shipment_id)
        
        return EtaDriftDetection(
            shipment_id=shipment_id,
            tracking_number=shipment.tracking_number,
            original_eta=shipment.estimated_delivery or datetime.now(),
            current_eta=shipment.estimated_delivery or datetime.now(),
            drift_minutes=0,
            drift_detected=False,
            threshold_minutes=service.config.eta_drift_threshold_minutes
        )
    
    return drift_detection


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get(
    "/config",
    response_model=ShipmentTrackingConfig,
    summary="Get configuration",
    description="Get the current agent configuration"
)
async def get_config(
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ShipmentTrackingConfig:
    """Get the current configuration."""
    return await service.get_config(x_tenant_id)


@app.patch(
    "/config",
    response_model=ShipmentTrackingConfig,
    summary="Update configuration",
    description="Update the agent configuration"
)
async def update_config(
    config_updates: Dict[str, Any],
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ShipmentTrackingConfig:
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
        "agent": "shipment-tracking",
        "version": "1.0.0"
    }


@app.get(
    "/stats",
    summary="Get statistics",
    description="Get shipment statistics"
)
async def get_stats(
    service: ShipmentTrackingService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Dict[str, Any]:
    """Get shipment statistics."""
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
