"""
Saas-api main FastAPI application.

This is the main entry point for the SaaS API service.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import get_db_session
from . import models
from .schemas import (
    OrganizationCreate,
    OrganizationResponse,
    PlanCreate,
    PlanResponse,
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
)
from .auth import (
    get_current_user,
    get_current_org,
    neon_auth_router,
)
from .routers import (
    organizations,
    plans,
    users,
    health,
)


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    print("Starting Saas-api...")
    
    # Initialize database
    from .database import init_db
    await init_db()
    
    print("Saas-api started successfully")
    
    yield
    
    # Shutdown
    print("Shutting down Saas-api...")
    from .database import close_db
    await close_db()
    print("Saas-api shutdown complete")


# ============================================================================
# Create App
# ============================================================================

app = FastAPI(
    title="Lanework SaaS API",
    description="SaaS layer API for Lanework - accounts, auth, billing, subscriptions",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Middleware
# ============================================================================

@app.middleware("http")
async def add_org_context(request: Request, call_next):
    """
    Middleware to add organization context to requests.
    
    This sets the current org_id for RLS based on the authenticated user.
    """
    # Get org_id from request state (set by auth middleware)
    org_id = getattr(request.state, "org_id", None)
    
    if org_id:
        # Set RLS context
        from saas_db.database import set_current_org_id
        set_current_org_id(org_id)
    
    response = await call_next(request)
    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    # Log the error
    print(f"Error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Internal server error"}},
    )


# ============================================================================
# Routers
# ============================================================================

# Auth router (Neon Auth)
app.include_router(neon_auth_router, prefix="/auth", tags=["auth"])

# Organizations
app.include_router(organizations.router, prefix="/organizations", tags=["organizations"])

# Plans
app.include_router(plans.router, prefix="/plans", tags=["plans"])

# Users
app.include_router(users.router, prefix="/users", tags=["users"])

# Health
app.include_router(health.router, prefix="/health", tags=["health"])


# ============================================================================
# Root
# ============================================================================

@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "service": "saas-api",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.saas_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
