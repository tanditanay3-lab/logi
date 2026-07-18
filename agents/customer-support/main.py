"""
Main application for the Customer Communication Agent.

This FastAPI application exposes the Customer Communication Agent API.
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

from .config import CustomerSupportConfig, get_default_config, settings
from .schemas import (
    ComplianceAlertListResponse,
    Conversation,
    ConversationCreate,
    ConversationListResponse,
    ConversationPriority,
    ConversationStatus,
    ConversationUpdate,
    EscalationRequest,
    EscalationResponse,
    NotificationRequest,
    NotificationResponse,
    NotificationType,
    ReplyRequest,
    ReplyResponse,
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
)
from .service import CustomerSupportService

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
    
    logger.info("Customer Communication Agent started")
    yield
    logger.info("Customer Communication Agent shutting down")


app = FastAPI(
    title="Customer Communication Agent",
    description="Lanework Customer Communication Agent API",
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
) -> CustomerSupportService:
    """Get the CustomerSupportService instance."""
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
    service = CustomerSupportService(
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
# Conversation Endpoints
# ============================================================================

@app.post(
    "/customer/conversations",
    response_model=Conversation,
    summary="Create a conversation",
    description="Create a new customer conversation"
)
async def create_conversation(
    conversation_data: ConversationCreate,
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Conversation:
    """Create a new customer conversation."""
    conversation, agent_task = await service.create_conversation(
        conversation_data=conversation_data,
        tenant_id=x_tenant_id
    )
    
    return conversation


@app.get(
    "/customer/conversations/{conversation_id}",
    response_model=Conversation,
    summary="Get a conversation",
    description="Get a single conversation by ID"
)
async def get_conversation(
    conversation_id: str,
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Conversation:
    """Get a conversation by ID."""
    conversation = await service.get_conversation(conversation_id, x_tenant_id)
    
    if not conversation:
        raise NotFoundException("conversation", conversation_id)
    
    return conversation


@app.get(
    "/customer/conversations",
    response_model=ConversationListResponse,
    summary="List conversations",
    description="List all customer conversations with optional filters"
)
async def list_conversations(
    customer_id: Optional[str] = Query(default=None),
    status: Optional[ConversationStatus] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ConversationListResponse:
    """List customer conversations."""
    conversations, total = await service.list_conversations(
        tenant_id=x_tenant_id,
        customer_id=customer_id,
        status=status,
        channel=channel,
        limit=limit,
        offset=offset
    )
    
    return ConversationListResponse(
        conversations=conversations,
        total=total,
        limit=limit,
        offset=offset
    )


@app.patch(
    "/customer/conversations/{conversation_id}",
    response_model=Conversation,
    summary="Update a conversation",
    description="Update conversation fields"
)
async def update_conversation(
    conversation_id: str,
    conversation_data: ConversationUpdate,
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Conversation:
    """Update a conversation."""
    conversation, agent_task = await service.update_conversation(
        conversation_id=conversation_id,
        conversation_data=conversation_data,
        tenant_id=x_tenant_id
    )
    
    if not conversation:
        raise NotFoundException("conversation", conversation_id)
    
    return conversation


# ============================================================================
# Reply Endpoints
# ============================================================================

@app.post(
    "/customer/conversations/{conversation_id}/reply",
    response_model=ReplyResponse,
    summary="Send a reply",
    description="Send a reply to a customer conversation"
)
async def send_reply(
    conversation_id: str,
    reply_data: ReplyRequest,
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ReplyResponse:
    """Send a reply to a conversation."""
    response, agent_task = await service.send_reply(
        conversation_id=conversation_id,
        reply_data=reply_data,
        tenant_id=x_tenant_id
    )
    
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Reply pending approval: {agent_task.id}")
    
    return response


# ============================================================================
# Escalation Endpoints
# ============================================================================

@app.post(
    "/customer/conversations/{conversation_id}/escalate",
    response_model=EscalationResponse,
    summary="Escalate a conversation",
    description="Escalate a conversation to a human agent"
)
async def escalate_conversation(
    conversation_id: str,
    escalation_data: EscalationRequest,
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> EscalationResponse:
    """Escalate a conversation."""
    response, agent_task = await service.escalate_conversation(
        conversation_id=conversation_id,
        escalation_data=escalation_data,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Notification Endpoints
# ============================================================================

@app.post(
    "/customer/notifications",
    response_model=NotificationResponse,
    summary="Send a notification",
    description="Send a proactive notification to a customer"
)
async def send_notification(
    notification_data: NotificationRequest,
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> NotificationResponse:
    """Send a proactive notification."""
    response, agent_task = await service.send_notification(
        notification_data=notification_data,
        tenant_id=x_tenant_id
    )
    
    if agent_task and agent_task.status == "pending_approval":
        logger.info(f"Notification pending approval: {agent_task.id}")
    
    return response


# ============================================================================
# Sentiment Analysis Endpoints
# ============================================================================

@app.post(
    "/customer/sentiment-analysis",
    response_model=SentimentAnalysisResponse,
    summary="Analyze sentiment",
    description="Analyze sentiment of a message"
)
async def analyze_sentiment(
    request: SentimentAnalysisRequest,
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> SentimentAnalysisResponse:
    """Analyze sentiment of a message."""
    response, agent_task = await service.analyze_sentiment(
        request=request,
        tenant_id=x_tenant_id
    )
    
    return response


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get(
    "/config",
    response_model=CustomerSupportConfig,
    summary="Get configuration",
    description="Get the current agent configuration"
)
async def get_config(
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> CustomerSupportConfig:
    """Get the current configuration."""
    return await service.get_config(x_tenant_id)


@app.patch(
    "/config",
    response_model=CustomerSupportConfig,
    summary="Update configuration",
    description="Update the agent configuration"
)
async def update_config(
    config_updates: Dict[str, Any],
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> CustomerSupportConfig:
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
        "agent": "customer-support",
        "version": "1.0.0"
    }


@app.get(
    "/stats",
    summary="Get statistics",
    description="Get customer support statistics"
)
async def get_stats(
    service: CustomerSupportService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Dict[str, Any]:
    """Get customer support statistics."""
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
