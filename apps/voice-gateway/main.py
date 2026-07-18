"""
Main application for the Voice Gateway.

This FastAPI application provides the voice interface for Lanework using LiveKit Agents.
It handles:
- Inbound phone calls (SIP)
- Outbound phone calls
- Speech-to-text (STT)
- Text-to-speech (TTS)
- Integration with the Conversation Router
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from packages.shared_types.exceptions import (
    LaneworkException,
    NotFoundException,
    PermissionException,
    ValidationException,
)

from .config import settings
from .livekit_client import LiveKitClient
from .voice_agent import VoiceAgent

logger = logging.getLogger(__name__)


# ============================================================================
# Application Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Initialize LiveKit client
    app.state.livekit_client = LiveKitClient()
    await app.state.livekit_client.initialize()
    
    # Initialize Voice Agent
    app.state.voice_agent = VoiceAgent(app.state.livekit_client)
    await app.state.voice_agent.initialize()
    
    logger.info("Voice Gateway started")
    yield
    
    # Cleanup
    await app.state.voice_agent.close()
    await app.state.livekit_client.close()
    logger.info("Voice Gateway shutting down")


app = FastAPI(
    title="Lanework Voice Gateway",
    description="Voice interface for Lanework using LiveKit Agents",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================================================
# Dependencies
# ============================================================================

async def get_livekit_client(request: Request) -> LiveKitClient:
    """Get the LiveKit client."""
    return request.app.state.livekit_client


async def get_voice_agent(request: Request) -> VoiceAgent:
    """Get the Voice Agent."""
    return request.app.state.voice_agent


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
        "service": "lanework-voice-gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get(
    "/health",
    summary="Health check",
    description="Check if the Voice Gateway is healthy"
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "voice-gateway",
        "version": "1.0.0",
        "livekit": "connected",
        "voice_agent": "ready"
    }


# ============================================================================
# Voice Call Endpoints
# ============================================================================

@app.post(
    "/calls",
    summary="Initiate a call",
    description="Initiate an outbound call or handle an inbound call"
)
async def handle_call(
    request: Request,
    voice_agent: VoiceAgent = Depends(get_voice_agent),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """
    Handle a voice call.
    
    This endpoint:
    - For inbound calls: Receives call from LiveKit and routes to Conversation Router
    - For outbound calls: Initiates a call through LiveKit
    """
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Get request body
    body = await request.json()
    
    # Handle the call
    result = await voice_agent.handle_call(
        call_data=body,
        tenant_id=x_tenant_id
    )
    
    return result


@app.get(
    "/calls/{call_id}",
    summary="Get call status",
    description="Get the status of a voice call"
)
async def get_call_status(
    call_id: str,
    voice_agent: VoiceAgent = Depends(get_voice_agent),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Get the status of a voice call."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    call_info = await voice_agent.get_call_info(call_id, x_tenant_id)
    
    if not call_info:
        raise NotFoundException("voice_call", call_id)
    
    return call_info


@app.post(
    "/calls/{call_id}/transcript",
    summary="Get call transcript",
    description="Get the transcript of a voice call"
)
async def get_call_transcript(
    call_id: str,
    voice_agent: VoiceAgent = Depends(get_voice_agent),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Get the transcript of a voice call."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    transcript = await voice_agent.get_call_transcript(call_id, x_tenant_id)
    
    if transcript is None:
        raise NotFoundException("voice_call", call_id)
    
    return {"call_id": call_id, "transcript": transcript}


@app.post(
    "/calls/{call_id}/escalate",
    summary="Escalate call to human",
    description="Escalate a voice call to a human agent"
)
async def escalate_call(
    call_id: str,
    reason: str = "",
    voice_agent: VoiceAgent = Depends(get_voice_agent),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Escalate a voice call to a human agent."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    success = await voice_agent.escalate_call(call_id, x_tenant_id, reason)
    
    if not success:
        raise NotFoundException("voice_call", call_id)
    
    return {"status": "escalated", "call_id": call_id, "reason": reason}


# ============================================================================
# STT/TTS Endpoints
# ============================================================================

@app.post(
    "/stt",
    summary="Speech to Text",
    description="Convert speech audio to text"
)
async def speech_to_text(
    request: Request,
    livekit_client: LiveKitClient = Depends(get_livekit_client),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Convert speech audio to text."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Get audio data
    body = await request.body()
    
    # Convert speech to text
    result = await livekit_client.speech_to_text(
        audio_data=body,
        tenant_id=x_tenant_id
    )
    
    return result


@app.post(
    "/tts",
    summary="Text to Speech",
    description="Convert text to speech audio"
)
async def text_to_speech(
    request: Request,
    livekit_client: LiveKitClient = Depends(get_livekit_client),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Convert text to speech audio."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Get text data
    body = await request.json()
    text = body.get("text", "")
    
    # Convert text to speech
    audio_data = await livekit_client.text_to_speech(
        text=text,
        tenant_id=x_tenant_id
    )
    
    # Return audio data
    from fastapi.responses import StreamingResponse
    import io
    
    return StreamingResponse(
        content=io.BytesIO(audio_data),
        media_type="audio/wav"
    )


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
