"""
Main application for the Chat Copilot.

This FastAPI application provides the chat interface for Lanework.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db import get_db_session
from packages.shared_types.exceptions import (
    LaneworkException,
    NotFoundException,
    PermissionException,
    ValidationException,
)

from .config import ChatCopilotConfig, get_default_config, settings
from .schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStats,
    ConversationListResponse,
    ConversationSummary,
)
from .service import ChatCopilotService

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
    
    logger.info("Chat Copilot started")
    yield
    logger.info("Chat Copilot shutting down")


app = FastAPI(
    title="Lanework Chat Copilot",
    description="Chat interface for Lanework - Route messages to appropriate agents",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Would be configured in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Dependencies
# ============================================================================

async def get_service(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> ChatCopilotService:
    """Get the ChatCopilotService instance."""
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
    service = ChatCopilotService(
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
# Chat Endpoints
# ============================================================================

@app.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send chat message",
    description="Send a message and get a response from the appropriate agent"
)
async def send_message(
    request: ChatRequest,
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ChatResponse:
    """
    Send a chat message and get a response.
    
    This endpoint:
    1. Creates or continues a conversation
    2. Routes the message to the appropriate agent via Conversation Router
    3. Returns the agent's response
    """
    # Set tenant ID
    request.tenant_id = x_tenant_id
    
    # Send the message
    response = await service.send_message(request)
    
    return response


@app.get(
    "/chat/suggested-prompts",
    response_model=List[str],
    summary="Get suggested prompts",
    description="Get suggested prompts for the chat interface"
)
async def get_suggested_prompts(
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> List[str]:
    """Get suggested prompts for the chat interface."""
    return service.config.suggested_prompts


# ============================================================================
# Conversation Endpoints
# ============================================================================

@app.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List conversations",
    description="List all conversations for a tenant"
)
async def list_conversations(
    participant_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ConversationListResponse:
    """List conversations."""
    return await service.list_conversations(
        tenant_id=x_tenant_id,
        participant_id=participant_id,
        limit=limit,
        offset=offset
    )


@app.get(
    "/conversations/{conversation_id}",
    response_model=Dict[str, Any],
    summary="Get conversation",
    description="Get a single conversation by ID"
)
async def get_conversation(
    conversation_id: str,
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> Dict[str, Any]:
    """Get a conversation by ID."""
    conversation = await service.get_conversation(conversation_id, x_tenant_id)
    
    if not conversation:
        raise NotFoundException("conversation", conversation_id)
    
    return conversation.model_dump()


@app.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    summary="Delete conversation",
    description="Delete a conversation"
)
async def delete_conversation(
    conversation_id: str,
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Delete a conversation."""
    success = await service.delete_conversation(conversation_id, x_tenant_id)
    
    if not success:
        raise NotFoundException("conversation", conversation_id)


# ============================================================================
# Streaming Chat Endpoint
# ============================================================================

@app.post(
    "/chat/stream",
    summary="Stream chat responses",
    description="Stream responses token by token (for typing effect)"
)
async def stream_chat(
    request: ChatRequest,
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """
    Stream chat responses token by token.
    
    This provides a better user experience with typing indicators.
    """
    # Set tenant ID
    request.tenant_id = x_tenant_id
    
    # Get the response
    response = await service.send_message(request)
    
    # Stream the response word by word
    async def generate_stream():
        words = response.response.split()
        for i, word in enumerate(words):
            # Add space before word (except first)
            if i > 0:
                yield f" {word}"
            else:
                yield word
            # Small delay for typing effect
            await asyncio.sleep(0.05)
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain"
    )


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.get(
    "/stats",
    response_model=ChatStats,
    summary="Get chat statistics",
    description="Get chat statistics for a tenant"
)
async def get_stats(
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ChatStats:
    """Get chat statistics."""
    return await service.get_stats(x_tenant_id)


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get(
    "/config",
    response_model=ChatCopilotConfig,
    summary="Get configuration",
    description="Get the current agent configuration"
)
async def get_config(
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ChatCopilotConfig:
    """Get the current configuration."""
    return await service.get_config(x_tenant_id)


@app.patch(
    "/config",
    response_model=ChatCopilotConfig,
    summary="Update configuration",
    description="Update the agent configuration"
)
async def update_config(
    config_updates: Dict[str, Any],
    service: ChatCopilotService = Depends(get_service),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
) -> ChatCopilotConfig:
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
        "agent": "chat-copilot",
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
