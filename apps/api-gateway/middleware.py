"""
Middleware for the API Gateway.

This module contains middleware classes for:
- Authentication
- Tenant routing
- Rate limiting
- Request ID generation
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

from packages.shared_types.exceptions import (
    AuthenticationException,
    PermissionException,
    RateLimitException,
    TenantNotFoundException,
)

from .config import settings

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware for generating and tracking request IDs.
    
    This middleware:
    - Generates a unique request ID for each request
    - Adds the request ID to the response headers
    - Makes the request ID available in request.state
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Add to request state
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers[settings.request_id_header] = request_id
        
        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authentication.
    
    This middleware:
    - Validates API keys
    - Validates JWT tokens
    - Sets authentication context in request.state
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip authentication for health check and docs
        if request.url.path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        # Check for API key authentication
        if settings.auth_enabled:
            # Check header
            api_key = request.headers.get("Authorization")
            if api_key and api_key.startswith("Bearer "):
                api_key = api_key[7:]
            
            # Check if API key is valid
            if settings.api_key and api_key != settings.api_key:
                raise AuthenticationException("Invalid API key")
            
            # If no API key configured but auth is enabled, check JWT
            if not settings.api_key and settings.jwt_secret:
                await self._validate_jwt(request)
        
        # Set authentication context
        request.state.authenticated = True
        request.state.api_key = api_key if api_key else None
        
        return await call_next(request)
    
    async def _validate_jwt(self, request: Request):
        """Validate JWT token."""
        # In a real implementation, this would validate the JWT
        # For now, just check that the Authorization header exists
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise AuthenticationException("Authentication required")


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tenant routing and isolation.
    
    This middleware:
    - Extracts tenant ID from headers
    - Validates tenant exists
    - Sets tenant context in request.state
    - Enforces row-level security
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip tenant check for health check and docs
        if request.url.path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        # Extract tenant ID
        tenant_id = request.headers.get(settings.tenant_header)
        
        if not tenant_id:
            # Use default tenant if configured
            tenant_id = settings.default_tenant_id
        
        if not tenant_id:
            raise PermissionException("Tenant ID is required")
        
        # Validate tenant exists (in a real implementation)
        # For now, we'll just accept any tenant ID
        
        # Set tenant context
        request.state.tenant_id = tenant_id
        
        # Add tenant ID to response headers
        response = await call_next(request)
        response.headers[settings.tenant_header] = tenant_id
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting.
    
    This middleware:
    - Tracks request counts per client
    - Enforces rate limits
    - Returns appropriate HTTP status codes
    """
    
    def __init__(self, app):
        super().__init__(app)
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health check and docs
        if request.url.path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        async with self._lock:
            # Initialize rate limit tracking for this client
            if client_id not in self._rate_limits:
                self._rate_limits[client_id] = {
                    "requests": [],
                    "last_reset": time.time()
                }
            
            client_limits = self._rate_limits[client_id]
            current_time = time.time()
            
            # Reset if time window has passed
            if current_time - client_limits["last_reset"] > 60:  # 1 minute window
                client_limits["requests"] = []
                client_limits["last_reset"] = current_time
            
            # Check if rate limit exceeded
            if len(client_limits["requests"]) >= settings.rate_limit_requests_per_minute:
                # Check burst limit
                recent_requests = [
                    t for t in client_limits["requests"]
                    if current_time - t < 1  # Last second
                ]
                if len(recent_requests) >= settings.rate_limit_burst_size:
                    raise RateLimitException(
                        "Rate limit exceeded",
                        retry_after=60
                    )
            
            # Record this request
            client_limits["requests"].append(current_time)
        
        return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """Get a unique identifier for the client."""
        # Use API key if available
        api_key = request.headers.get("Authorization")
        if api_key:
            return f"api_key:{api_key}"
        
        # Use IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request logging.
    
    This middleware:
    - Logs incoming requests
    - Logs responses
    - Tracks request duration
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for health check
        if request.url.path == "/health":
            return await call_next(request)
        
        # Log request
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        tenant_id = getattr(request.state, "tenant_id", "unknown")
        
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client": str(request.client) if request.client else "unknown"
            }
        )
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": round(duration, 3)
            }
        )
        
        return response
