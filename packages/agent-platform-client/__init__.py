"""
Agent Platform Client - The ONLY way to call the agent platform from SaaS layer.

This package provides a typed client for calling the existing agent platform's
API Gateway. All calls to the agent platform must go through this client.

The agent platform expects:
- tenant_id in format: tenant_<uuid>
- Authorization: Bearer <tenant_api_key> header
- X-Tenant-ID header for explicit tenant context
"""

from .client import AgentPlatformClient
from .schemas import (
    AgentTaskResponse,
    ShipmentCreate,
    ShipmentResponse,
    RouteOptimizeRequest,
    RouteResponse,
    InventoryItemCreate,
    InventoryItemResponse,
)

__all__ = [
    "AgentPlatformClient",
    "AgentTaskResponse",
    "ShipmentCreate",
    "ShipmentResponse",
    "RouteOptimizeRequest",
    "RouteResponse",
    "InventoryItemCreate",
    "InventoryItemResponse",
]
