"""
MCP Client for the Tool Bus.

This client is used by agents to call tools through the MCP protocol.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel

from .tool_definitions import (
    ToolCall,
    ToolDefinition,
    ToolError,
    ToolResult,
    TOOL_REGISTRY,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPClientConfig:
    """Configuration for the MCP Client."""
    base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_reset_timeout: float = 60.0
    cache_enabled: bool = True
    cache_ttl: float = 300.0


@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern."""
    failures: int = 0
    last_failure_time: Optional[float] = None
    is_open: bool = False


class MCPClient:
    """
    MCP Client for calling tools through the Tool Bus.
    
    This client handles:
    - Tool discovery and validation
    - Tool calls with retries and circuit breaking
    - Caching of tool results
    - Error handling and graceful degradation
    """
    
    def __init__(self, config: Optional[MCPClientConfig] = None):
        self.config = config or MCPClientConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._tool_cache: Dict[str, ToolDefinition] = {}
        self._result_cache: Dict[str, Any] = {}
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the client."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            if self.config.api_key:
                {"Authorization": f"Bearer {self.config.api_key}"}
        )
        
        # Load tool definitions
        await self._load_tool_definitions()
        
    async def close(self):
        """Close the client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        
    @asynccontextmanager
    async def session(self):
        """Context manager for client session."""
        await self.initialize()
        try:
            yield self
        finally:
            await self.close()
    
    async def _load_tool_definitions(self):
        """Load tool definitions from the server."""
        try:
            # For now, use the local tool registry
            # In production, this would fetch from the MCP server
            for integration_type, tools in TOOL_REGISTRY.items():
                for tool in tools:
                    self._tool_cache[tool.name] = tool
        except Exception as e:
            logger.error(f"Failed to load tool definitions: {e}")
            # Fall back to local definitions
            for tool in TOOL_REGISTRY.get("carrier", []):
                self._tool_cache[tool.name] = tool
    
    def get_tool_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get the definition for a tool."""
        return self._tool_cache.get(tool_name)
    
    def list_tools(
        self,
        integration_type: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[ToolDefinition]:
        """List available tools."""
        tools = list(self._tool_cache.values())
        
        if integration_type:
            tools = [t for t in tools if t.integration_type == integration_type]
        if category:
            tools = [t for t in tools if t.category == category]
            
        return tools
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tenant_id: str,
        agent_type: str,
        agent_task_id: Optional[str] = None,
        timeout: Optional[float] = None,
        retry_policy: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        Call a tool through the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool
            tenant_id: Tenant ID
            agent_type: Type of agent making the call
            agent_task_id: Optional reference to AgentTask
            timeout: Optional timeout override
            retry_policy: Optional retry policy override
            
        Returns:
            ToolResult with the result or error
        """
        # Generate call ID
        call_id = f"call_{int(time.time() * 1000)}_{hash(tool_name) % 10000}"
        
        # Get tool definition
        tool_def = self.get_tool_definition(tool_name)
        if not tool_def:
            return ToolResult(
                call_id=call_id,
                status="error",
                error=f"Tool '{tool_name}' not found",
                duration_ms=0,
                timestamp=datetime.utcnow()
            )
        
        # Validate arguments
        validation_error = self._validate_arguments(tool_def, arguments)
        if validation_error:
            return ToolResult(
                call_id=call_id,
                status="error",
                error=validation_error,
                duration_ms=0,
                timestamp=datetime.utcnow()
            )
        
        # Check circuit breaker
        if self._is_circuit_open(tool_name):
            return ToolResult(
                call_id=call_id,
                status="error",
                error=f"Circuit breaker open for tool '{tool_name}'",
                duration_ms=0,
                timestamp=datetime.utcnow()
            )
        
        # Check cache
        cache_key = self._get_cache_key(tool_name, arguments)
        if self.config.cache_enabled and cache_key in self._result_cache:
            cached = self._result_cache[cache_key]
            if time.time() - cached.get("timestamp", 0) < self.config.cache_ttl:
                return ToolResult(
                    call_id=call_id,
                    status="success",
                    result=cached["result"],
                    duration_ms=0,
                    timestamp=datetime.utcnow()
                )
        
        # Create tool call
        tool_call = ToolCall(
            tool_name=tool_name,
            arguments=arguments,
            call_id=call_id,
            tenant_id=tenant_id,
            agent_type=agent_type,
            agent_task_id=agent_task_id,
            timestamp=datetime.utcnow()
        )
        
        # Execute with retries
        start_time = time.time()
        last_error: Optional[Exception] = None
        retry_count = 0
        
        effective_timeout = timeout or tool_def.timeout_seconds
        effective_retry_policy = retry_policy or tool_def.retry_policy
        max_retries = effective_retry_policy.get("max_retries", self.config.max_retries)
        
        for attempt in range(max_retries + 1):
            try:
                result = await self._execute_tool_call(tool_call, effective_timeout)
                
                if result.status == "success":
                    # Cache successful result
                    if self.config.cache_enabled:
                        self._result_cache[cache_key] = {
                            "result": result.result,
                            "timestamp": time.time()
                        }
                    
                    # Reset circuit breaker
                    self._reset_circuit_breaker(tool_name)
                    
                    duration_ms = int((time.time() - start_time) * 1000)
                    return ToolResult(
                        call_id=call_id,
                        status="success",
                        result=result.result,
                        duration_ms=duration_ms,
                        timestamp=datetime.utcnow(),
                        retry_count=retry_count
                    )
                else:
                    last_error = Exception(result.error or "Unknown error")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Tool call failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                
                # Record failure for circuit breaker
                self._record_failure(tool_name)
                
            retry_count += 1
            
            # Wait before retry
            if attempt < max_retries:
                delay = effective_retry_policy.get("backoff_multiplier", self.config.retry_backoff) ** attempt
                await asyncio.sleep(delay)
        
        # All retries failed
        error_msg = str(last_error) if last_error else "Unknown error"
        duration_ms = int((time.time() - start_time) * 1000)
        
        return ToolResult(
            call_id=call_id,
            status="error",
            error=error_msg,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow(),
            retry_count=retry_count
        )
    
    async def _execute_tool_call(
        self,
        tool_call: ToolCall,
        timeout: float
    ) -> ToolResult:
        """Execute a tool call."""
        if not self._client:
            raise Exception("Client not initialized")
        
        try:
            # For now, simulate tool execution
            # In production, this would call the actual MCP server
            result = await self._simulate_tool_execution(tool_call)
            return result
            
        except httpx.TimeoutException:
            return ToolResult(
                call_id=tool_call.call_id,
                status="timeout",
                error=f"Tool '{tool_call.tool_name}' timed out after {timeout}s",
                duration_ms=0,
                timestamp=datetime.utcnow()
            )
        except httpx.HTTPStatusError as e:
            return ToolResult(
                call_id=tool_call.call_id,
                status="error",
                error=f"HTTP {e.response.status_code}: {e.response.text}",
                duration_ms=0,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                call_id=tool_call.call_id,
                status="error",
                error=str(e),
                duration_ms=0,
                timestamp=datetime.utcnow()
            )
    
    async def _simulate_tool_execution(self, tool_call: ToolCall) -> ToolResult:
        """
        Simulate tool execution for development/testing.
        
        In production, this would call the actual MCP server.
        """
        # Simulate different tool types
        if tool_call.tool_name.startswith("carrier."):
            return await self._simulate_carrier_tool(tool_call)
        elif tool_call.tool_name.startswith("tms."):
            return await self._simulate_tms_tool(tool_call)
        elif tool_call.tool_name.startswith("telematics."):
            return await self._simulate_telematics_tool(tool_call)
        elif tool_call.tool_name.startswith("maps."):
            return await self._simulate_maps_tool(tool_call)
        elif tool_call.tool_name.startswith("sip."):
            return await self._simulate_sip_tool(tool_call)
        elif tool_call.tool_name.startswith("notification."):
            return await self._simulate_notification_tool(tool_call)
        else:
            return ToolResult(
                call_id=tool_call.call_id,
                status="error",
                error=f"Unknown tool: {tool_call.tool_name}",
                duration_ms=0,
                timestamp=datetime.utcnow()
            )
    
    async def _simulate_carrier_tool(self, tool_call: ToolCall) -> ToolResult:
        """Simulate carrier tool execution."""
        import random
        
        if tool_call.tool_name == "carrier.get_tracking_info":
            tracking_number = tool_call.arguments.get("tracking_number", "UNKNOWN")
            carrier = tool_call.arguments.get("carrier", "UNKNOWN")
            
            # Simulate tracking info
            result = {
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status": random.choice(["IN_TRANSIT", "DELIVERED", "DELAYED", "PENDING"]),
                "current_location": {
                    "lat": random.uniform(30, 40),
                    "lng": random.uniform(-120, -70)
                },
                "estimated_delivery": datetime.utcnow().isoformat(),
                "events": [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "type": "DEPARTURE",
                        "description": "Departed origin",
                        "location": {"lat": 35.0, "lng": -90.0}
                    }
                ]
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(100, 500),
                timestamp=datetime.utcnow()
            )
        
        elif tool_call.tool_name == "carrier.create_shipment":
            result = {
                "tracking_number": f"TRK{random.randint(1000000000, 9999999999)}",
                "carrier": tool_call.arguments.get("carrier", "UNKNOWN"),
                "status": "CREATED"
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(200, 1000),
                timestamp=datetime.utcnow()
            )
        
        elif tool_call.tool_name == "carrier.get_quote":
            result = {
                "cost": random.uniform(50, 500),
                "currency": "USD",
                "transit_time_hours": random.randint(24, 72),
                "service_level": tool_call.arguments.get("service_level", "STANDARD")
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(100, 500),
                timestamp=datetime.utcnow()
            )
        
        return ToolResult(
            call_id=tool_call.call_id,
            status="error",
            error=f"Unknown carrier tool: {tool_call.tool_name}",
            duration_ms=0,
            timestamp=datetime.utcnow()
        )
    
    async def _simulate_tms_tool(self, tool_call: ToolCall) -> ToolResult:
        """Simulate TMS tool execution."""
        import random
        
        if tool_call.tool_name == "tms.get_order":
            result = {
                "order_id": tool_call.arguments.get("order_id", "ORD001"),
                "status": random.choice(["PENDING", "PROCESSING", "SHIPPED", "DELIVERED"]),
                "items": [
                    {
                        "sku": "ITEM001",
                        "quantity": random.randint(1, 10),
                        "description": "Sample Item"
                    }
                ]
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(50, 200),
                timestamp=datetime.utcnow()
            )
        
        return ToolResult(
            call_id=tool_call.call_id,
            status="error",
            error=f"Unknown TMS tool: {tool_call.tool_name}",
            duration_ms=0,
            timestamp=datetime.utcnow()
        )
    
    async def _simulate_telematics_tool(self, tool_call: ToolCall) -> ToolResult:
        """Simulate telematics tool execution."""
        import random
        
        if tool_call.tool_name == "telematics.get_vehicle_location":
            result = {
                "vehicle_id": tool_call.arguments.get("vehicle_id", "VEH001"),
                "location": {
                    "lat": random.uniform(30, 40),
                    "lng": random.uniform(-120, -70)
                },
                "timestamp": datetime.utcnow().isoformat(),
                "speed_mph": random.uniform(0, 70)
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(50, 200),
                timestamp=datetime.utcnow()
            )
        
        elif tool_call.tool_name == "telematics.get_driver_hos":
            result = {
                "driver_id": tool_call.arguments.get("driver_id", "DRV001"),
                "remaining_duty_hours": random.uniform(0, 14),
                "remaining_drive_hours": random.uniform(0, 11),
                "status": random.choice(["OK", "WARNING", "VIOLATION"])
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(50, 200),
                timestamp=datetime.utcnow()
            )
        
        return ToolResult(
            call_id=tool_call.call_id,
            status="error",
            error=f"Unknown telematics tool: {tool_call.tool_name}",
            duration_ms=0,
            timestamp=datetime.utcnow()
        )
    
    async def _simulate_maps_tool(self, tool_call: ToolCall) -> ToolResult:
        """Simulate maps tool execution."""
        import random
        
        if tool_call.tool_name == "maps.get_distance_matrix":
            origins = tool_call.arguments.get("origins", [])
            destinations = tool_call.arguments.get("destinations", [])
            
            result = {
                "origins": origins,
                "destinations": destinations,
                "distances": [[random.uniform(1, 100) for _ in destinations] for _ in origins],
                "durations": [[random.randint(30, 300) for _ in destinations] for _ in origins]
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(100, 500),
                timestamp=datetime.utcnow()
            )
        
        elif tool_call.tool_name == "maps.get_directions":
            result = {
                "origin": tool_call.arguments.get("origin", {}),
                "destination": tool_call.arguments.get("destination", {}),
                "distance_miles": random.uniform(1, 100),
                "duration_minutes": random.randint(30, 300),
                "polyline": "encoded_polyline_string"
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(100, 500),
                timestamp=datetime.utcnow()
            )
        
        elif tool_call.tool_name == "maps.geocode":
            address = tool_call.arguments.get("address", "")
            result = {
                "address": address,
                "location": {
                    "lat": random.uniform(30, 40),
                    "lng": random.uniform(-120, -70)
                },
                "formatted_address": f"Formatted: {address}"
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(50, 200),
                timestamp=datetime.utcnow()
            )
        
        return ToolResult(
            call_id=tool_call.call_id,
            status="error",
            error=f"Unknown maps tool: {tool_call.tool_name}",
            duration_ms=0,
            timestamp=datetime.utcnow()
        )
    
    async def _simulate_sip_tool(self, tool_call: ToolCall) -> ToolResult:
        """Simulate SIP tool execution."""
        import random
        
        if tool_call.tool_name == "sip.make_call":
            result = {
                "call_id": f"call_{random.randint(1000000000, 9999999999)}",
                "status": "DIALING",
                "phone_number": tool_call.arguments.get("phone_number", "UNKNOWN")
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(200, 1000),
                timestamp=datetime.utcnow()
            )
        
        return ToolResult(
            call_id=tool_call.call_id,
            status="error",
            error=f"Unknown SIP tool: {tool_call.tool_name}",
            duration_ms=0,
            timestamp=datetime.utcnow()
        )
    
    async def _simulate_notification_tool(self, tool_call: ToolCall) -> ToolResult:
        """Simulate notification tool execution."""
        import random
        
        if tool_call.tool_name == "notification.send_email":
            result = {
                "status": "SENT",
                "to": tool_call.arguments.get("to", "UNKNOWN"),
                "subject": tool_call.arguments.get("subject", ""),
                "message_id": f"msg_{random.randint(1000000000, 9999999999)}"
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(100, 500),
                timestamp=datetime.utcnow()
            )
        
        elif tool_call.tool_name == "notification.send_sms":
            result = {
                "status": "SENT",
                "to": tool_call.arguments.get("to", "UNKNOWN"),
                "message": tool_call.arguments.get("message", ""),
                "message_id": f"sms_{random.randint(1000000000, 9999999999)}"
            }
            
            return ToolResult(
                call_id=tool_call.call_id,
                status="success",
                result=result,
                duration_ms=random.randint(100, 500),
                timestamp=datetime.utcnow()
            )
        
        return ToolResult(
            call_id=tool_call.call_id,
            status="error",
            error=f"Unknown notification tool: {tool_call.tool_name}",
            duration_ms=0,
            timestamp=datetime.utcnow()
        )
    
    def _validate_arguments(
        self,
        tool_def: ToolDefinition,
        arguments: Dict[str, Any]
    ) -> Optional[str]:
        """Validate tool arguments against the tool definition."""
        required_params = {p.name for p in tool_def.parameters if p.required}
        provided_params = set(arguments.keys())
        
        # Check for missing required parameters
        missing = required_params - provided_params
        if missing:
            return f"Missing required parameters: {', '.join(missing)}"
        
        # Check for extra parameters
        allowed_params = {p.name for p in tool_def.parameters}
        extra = provided_params - allowed_params
        if extra:
            return f"Unknown parameters: {', '.join(extra)}"
        
        # Validate parameter types
        for param in tool_def.parameters:
            if param.name in arguments:
                error = self._validate_parameter_type(param, arguments[param.name])
                if error:
                    return error
        
        return None
    
    def _validate_parameter_type(
        self,
        param: ToolParameter,
        value: Any
    ) -> Optional[str]:
        """Validate a parameter value against its type definition."""
        if param.type == "string":
            if not isinstance(value, str):
                return f"Parameter '{param.name}' must be a string"
        elif param.type == "number":
            if not isinstance(value, (int, float)):
                return f"Parameter '{param.name}' must be a number"
            if param.min is not None and value < param.min:
                return f"Parameter '{param.name}' must be >= {param.min}"
            if param.max is not None and value > param.max:
                return f"Parameter '{param.name}' must be <= {param.max}"
        elif param.type == "boolean":
            if not isinstance(value, bool):
                return f"Parameter '{param.name}' must be a boolean"
        elif param.type == "array":
            if not isinstance(value, list):
                return f"Parameter '{param.name}' must be an array"
        elif param.type == "object":
            if not isinstance(value, dict):
                return f"Parameter '{param.name}' must be an object"
        elif param.enum and value not in param.enum:
            return f"Parameter '{param.name}' must be one of: {', '.join(param.enum)}"
        
        return None
    
    def _is_circuit_open(self, tool_name: str) -> bool:
        """Check if circuit breaker is open for a tool."""
        if not self.config.circuit_breaker_enabled:
            return False
        
        cb = self._circuit_breakers.get(tool_name)
        if not cb:
            return False
        
        if not cb.is_open:
            return False
        
        # Check if reset timeout has passed
        if cb.last_failure_time:
            elapsed = time.time() - cb.last_failure_time
            if elapsed > self.config.circuit_breaker_reset_timeout:
                cb.is_open = False
                cb.failures = 0
                return False
        
        return True
    
    def _record_failure(self, tool_name: str):
        """Record a failure for circuit breaker."""
        if not self.config.circuit_breaker_enabled:
            return
        
        if tool_name not in self._circuit_breakers:
            self._circuit_breakers[tool_name] = CircuitBreakerState()
        
        cb = self._circuit_breakers[tool_name]
        cb.failures += 1
        cb.last_failure_time = time.time()
        
        if cb.failures >= self.config.circuit_breaker_failure_threshold:
            cb.is_open = True
    
    def _reset_circuit_breaker(self, tool_name: str):
        """Reset circuit breaker for a tool."""
        if tool_name in self._circuit_breakers:
            self._circuit_breakers[tool_name] = CircuitBreakerState()
    
    def _get_cache_key(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generate a cache key for a tool call."""
        # Sort arguments for consistent cache key
        sorted_args = json.dumps(arguments, sort_keys=True)
        return f"{tool_name}:{sorted_args}"
