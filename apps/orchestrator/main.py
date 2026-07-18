"""
Main application for the Lanework Orchestrator.

This FastAPI application exposes the orchestration layer APIs including:
- Conversation Router
- Task/Event Orchestrator
- Planner
- Agent Registry
- Guardrails Engine
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db import get_db_session
from packages.shared_types.schemas import (
    AgentTask,
    AgentType,
    Config,
    TrustLevel,
)
from packages.shared_types.exceptions import (
    LaneworkException,
    NotFoundException,
    PermissionException,
    ValidationException,
)
from packages.tool_bus.mcp_client import MCPClient

from .config import settings
from .graphs import (
    ConversationRouterGraph,
    PlannerGraph,
    TaskOrchestratorGraph,
)
from .schemas import (
    AgentInfo,
    ConversationRequest,
    ConversationResponse,
    GuardrailsCheckRequest,
    GuardrailsCheckResponse,
    PlanRequest,
    PlanResponse,
    TaskRequest,
    TaskResponse,
)
from .services import (
    AgentRegistry,
    ConversationRouterService,
    GuardrailsEngine,
    PlannerService,
    TaskOrchestratorService,
)

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
    
    # Initialize services
    tool_client = MCPClient()
    await tool_client.initialize()
    
    app.state.tool_client = tool_client
    app.state.conversation_router = ConversationRouterGraph(tool_client)
    app.state.task_orchestrator = TaskOrchestratorGraph(tool_client)
    app.state.planner = PlannerGraph(tool_client)
    app.state.agent_registry = AgentRegistry()
    app.state.guardrails_engine = GuardrailsEngine()
    
    logger.info("Orchestrator started")
    yield
    
    # Cleanup
    await tool_client.close()
    logger.info("Orchestrator shutting down")


app = FastAPI(
    title="Lanework Orchestrator",
    description="Agent Orchestration Layer for Lanework",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================================================
# Dependencies
# ============================================================================

async def get_tool_client(request: Request) -> MCPClient:
    """Get the MCP client."""
    return request.app.state.tool_client


async def get_conversation_router(request: Request) -> ConversationRouterGraph:
    """Get the Conversation Router graph."""
    return request.app.state.conversation_router


async def get_task_orchestrator(request: Request) -> TaskOrchestratorGraph:
    """Get the Task Orchestrator graph."""
    return request.app.state.task_orchestrator


async def get_planner(request: Request) -> PlannerGraph:
    """Get the Planner graph."""
    return request.app.state.planner


async def get_agent_registry(request: Request) -> AgentRegistry:
    """Get the Agent Registry."""
    return request.app.state.agent_registry


async def get_guardrails_engine(request: Request) -> GuardrailsEngine:
    """Get the Guardrails Engine."""
    return request.app.state.guardrails_engine


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
# Conversation Router Endpoints
# ============================================================================

@app.post(
    "/conversation",
    response_model=ConversationResponse,
    summary="Route conversation",
    description="Route a conversation to the appropriate agent"
)
async def route_conversation(
    request: ConversationRequest,
    conversation_router: ConversationRouterGraph = Depends(get_conversation_router),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> ConversationResponse:
    """
    Route a conversation to the appropriate agent.
    
    This endpoint:
    1. Extracts intent from the message
    2. Routes to the appropriate agent
    3. Handles approval workflows if needed
    4. Returns the agent's response
    """
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Set tenant ID
    if x_tenant_id:
        request.tenant_id = x_tenant_id
    elif settings.tenant_id:
        request.tenant_id = settings.tenant_id
    else:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    
    # Run the conversation router
    response = await conversation_router.run(request)
    
    return response


# ============================================================================
# Task Orchestrator Endpoints
# ============================================================================

@app.post(
    "/tasks",
    response_model=TaskResponse,
    summary="Execute a task",
    description="Execute a task through the orchestrator"
)
async def execute_task(
    request: TaskRequest,
    task_orchestrator: TaskOrchestratorGraph = Depends(get_task_orchestrator),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> TaskResponse:
    """
    Execute a task through the orchestrator.
    
    This endpoint:
    1. Validates the task request
    2. Checks guardrails
    3. Checks trust levels
    4. Creates AgentTask records
    5. Routes to the appropriate agent
    6. Handles approval workflows
    """
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Set tenant ID
    if x_tenant_id:
        request.tenant_id = x_tenant_id
    elif settings.tenant_id:
        request.tenant_id = settings.tenant_id
    else:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    
    # Run the task orchestrator
    response = await task_orchestrator.run(request)
    
    return response


# ============================================================================
# Planner Endpoints
# ============================================================================

@app.post(
    "/plan",
    response_model=PlanResponse,
    summary="Create a plan",
    description="Create a plan to achieve a goal"
)
async def create_plan(
    request: PlanRequest,
    planner: PlannerGraph = Depends(get_planner),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> PlanResponse:
    """
    Create a plan to achieve a goal.
    
    This endpoint:
    1. Analyzes the goal and constraints
    2. Generates a plan with steps
    3. Validates the plan
    4. Returns the plan
    """
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Set tenant ID
    if x_tenant_id:
        request.tenant_id = x_tenant_id
    elif settings.tenant_id:
        request.tenant_id = settings.tenant_id
    else:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    
    # Run the planner
    response = await planner.run(request)
    
    return response


# ============================================================================
# Agent Registry Endpoints
# ============================================================================

@app.get(
    "/agents",
    response_model=List[AgentInfo],
    summary="List agents",
    description="List all registered agents"
)
async def list_agents(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> List[AgentInfo]:
    """List all registered agents."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    return await agent_registry.list_agents()


@app.get(
    "/agents/{agent_type}",
    response_model=AgentInfo,
    summary="Get agent info",
    description="Get information about a specific agent"
)
async def get_agent(
    agent_type: AgentType,
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> AgentInfo:
    """Get information about a specific agent."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    agent_info = await agent_registry.get_agent(agent_type)
    
    if not agent_info:
        raise NotFoundException("agent", str(agent_type))
    
    return agent_info


@app.post(
    "/agents/{agent_type}/register",
    response_model=AgentInfo,
    summary="Register an agent",
    description="Register a new agent"
)
async def register_agent(
    agent_type: AgentType,
    agent_info: AgentInfo,
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> AgentInfo:
    """Register a new agent."""
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    return await agent_registry.register_agent(agent_info)


# ============================================================================
# Guardrails Endpoints
# ============================================================================

@app.post(
    "/guardrails/check",
    response_model=GuardrailsCheckResponse,
    summary="Check guardrails",
    description="Check if an action is allowed by guardrails"
)
async def check_guardrails(
    request: GuardrailsCheckRequest,
    guardrails_engine: GuardrailsEngine = Depends(get_guardrails_engine),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization")
) -> GuardrailsCheckResponse:
    """
    Check if an action is allowed by guardrails.
    
    This endpoint:
    1. Validates the action against tenant policies
    2. Checks for compliance violations
    3. Returns whether the action is allowed
    """
    # Verify authentication
    if settings.api_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        api_key = authorization[7:]
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Set tenant ID
    if x_tenant_id:
        request.tenant_id = x_tenant_id
    elif settings.tenant_id:
        request.tenant_id = settings.tenant_id
    else:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    
    return await guardrails_engine.check(request)


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get(
    "/health",
    summary="Health check",
    description="Check if the orchestrator is healthy"
)
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "orchestrator",
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
