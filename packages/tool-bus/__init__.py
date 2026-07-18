"""
Tool/Integration Bus for Lanework

This package provides the MCP-based tool bus that all agents use to call external systems.
"""

from .mcp_client import MCPClient, MCPClientConfig
from .mcp_server import MCPServer, MCPServerConfig
from .tool_definitions import (
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolCall,
)
from .integrations import (
    CarrierIntegration,
    TMSIntegration,
    TelematicsIntegration,
    MapsIntegration,
    SIPIntegration,
)

__all__ = [
    # MCP Client
    "MCPClient",
    "MCPClientConfig",
    # MCP Server
    "MCPServer",
    "MCPServerConfig",
    # Tool Definitions
    "ToolDefinition",
    "ToolParameter",
    "ToolResult",
    "ToolCall",
    # Integrations
    "CarrierIntegration",
    "TMSIntegration",
    "TelematicsIntegration",
    "MapsIntegration",
    "SIPIntegration",
]
