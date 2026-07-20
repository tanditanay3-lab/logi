"""
Agent Platform Client implementation.

This is the sanctioned client for calling the agent platform's API Gateway.
All calls must go through this client - never call agent services directly.
"""

import os
from typing import Optional, Dict, Any
import httpx
from pydantic import BaseModel

from .schemas import (
    AgentTaskResponse,
    ShipmentCreate,
    ShipmentResponse,
    RouteOptimizeRequest,
    RouteResponse,
    InventoryItemCreate,
    InventoryItemResponse,
)


class AgentPlatformClient:
    """
    Client for the Agent Platform API Gateway.
    
    The agent platform expects:
    - tenant_id in format: tenant_<uuid>
    - Authorization: Bearer <tenant_api_key> header
    - X-Tenant-ID header for explicit tenant context
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the API Gateway (default from env)
            api_key: API key for authentication (default from env)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv(
            "AGENT_PLATFORM_URL",
            "http://localhost:8001"  # Default to local API Gateway
        )
        self.api_key = api_key or os.getenv("AGENT_PLATFORM_API_KEY")
        self.timeout = timeout
        
        # Create HTTP client
        self._client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def _get_headers(self, tenant_id: str) -> Dict[str, str]:
        """Get headers for a request."""
        headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": tenant_id,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _format_tenant_id(self, org_id: str) -> str:
        """
        Format the organization ID as tenant_id expected by agent platform.
        
        Agent platform expects: tenant_<uuid>
        SaaS layer uses: org_<uuid>
        """
        if org_id.startswith("org_"):
            uuid_part = org_id[4:]
            return f"tenant_{uuid_part}"
        return f"tenant_{org_id}"
    
    # ========================================================================
    # Shipment Tracking Agent (/shipments)
    # ========================================================================
    
    async def create_shipment(
        self,
        org_id: str,
        shipment: ShipmentCreate
    ) -> ShipmentResponse:
        """Create a new shipment."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        url = f"{self.base_url}/shipments"
        response = await self._client.post(
            url,
            json=shipment.model_dump(),
            headers=headers
        )
        response.raise_for_status()
        return ShipmentResponse(**response.json())
    
    async def get_shipment(
        self,
        org_id: str,
        shipment_id: str
    ) -> ShipmentResponse:
        """Get a shipment by ID."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        url = f"{self.base_url}/shipments/{shipment_id}"
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        return ShipmentResponse(**response.json())
    
    async def list_shipments(
        self,
        org_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List shipments for an organization."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        
        url = f"{self.base_url}/shipments"
        response = await self._client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    # ========================================================================
    # Route Optimization Agent (/routes)
    # ========================================================================
    
    async def optimize_route(
        self,
        org_id: str,
        request: RouteOptimizeRequest
    ) -> RouteResponse:
        """Optimize routes."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        url = f"{self.base_url}/routes/optimize"
        response = await self._client.post(
            url,
            json=request.model_dump(),
            headers=headers
        )
        response.raise_for_status()
        return RouteResponse(**response.json())
    
    async def create_route(
        self,
        org_id: str,
        route_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new route."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        url = f"{self.base_url}/routes"
        response = await self._client.post(
            url,
            json=route_data,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    # ========================================================================
    # Inventory Management Agent (/inventory)
    # ========================================================================
    
    async def create_inventory_item(
        self,
        org_id: str,
        item: InventoryItemCreate
    ) -> InventoryItemResponse:
        """Create a new inventory item."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        url = f"{self.base_url}/inventory/items"
        response = await self._client.post(
            url,
            json=item.model_dump(),
            headers=headers
        )
        response.raise_for_status()
        return InventoryItemResponse(**response.json())
    
    async def get_inventory_item(
        self,
        org_id: str,
        item_id: str
    ) -> InventoryItemResponse:
        """Get an inventory item by ID."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        url = f"{self.base_url}/inventory/items/{item_id}"
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        return InventoryItemResponse(**response.json())
    
    # ========================================================================
    # Agent Tasks (/agent-tasks)
    # ========================================================================
    
    async def get_agent_task(
        self,
        org_id: str,
        task_id: str
    ) -> AgentTaskResponse:
        """Get an AgentTask by ID."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        url = f"{self.base_url}/agent-tasks/{task_id}"
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        return AgentTaskResponse(**response.json())
    
    async def list_agent_tasks(
        self,
        org_id: str,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List AgentTasks for an organization."""
        tenant_id = self._format_tenant_id(org_id)
        headers = self._get_headers(tenant_id)
        
        params = {"limit": limit, "offset": offset}
        if agent_type:
            params["agent_type"] = agent_type
        if status:
            params["status"] = status
        
        url = f"{self.base_url}/agent-tasks"
        response = await self._client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    # ========================================================================
    # Health Check
    # ========================================================================
    
    async def health_check(self) -> bool:
        """Check if the agent platform is healthy."""
        try:
            url = f"{self.base_url}/health"
            response = await self._client.get(url, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False


# Global client instance
_agent_platform_client: Optional[AgentPlatformClient] = None


def get_agent_platform_client() -> AgentPlatformClient:
    """Get the global agent platform client instance."""
    global _agent_platform_client
    if _agent_platform_client is None:
        _agent_platform_client = AgentPlatformClient()
    return _agent_platform_client
