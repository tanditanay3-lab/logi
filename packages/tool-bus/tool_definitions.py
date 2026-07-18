"""
Tool definitions for the MCP-based Tool Bus.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, boolean, etc.)")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether the parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value")
    enum: Optional[List[str]] = Field(default=None, description="Allowed values for enum types")
    min: Optional[Union[int, float]] = Field(default=None, description="Minimum value for numbers")
    max: Optional[Union[int, float]] = Field(default=None, description="Maximum value for numbers")


class ToolDefinition(BaseModel):
    """Definition of a tool that can be called through the Tool Bus."""
    name: str = Field(..., description="Unique tool name")
    description: str = Field(..., description="Tool description")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    returns: str = Field(..., description="Description of return value")
    integration_type: str = Field(..., description="Type of integration (carrier, tms, telematics, maps, sip)")
    category: str = Field(..., description="Tool category")
    tags: List[str] = Field(default_factory=list, description="Tool tags")
    timeout_seconds: int = Field(default=30, description="Default timeout for tool calls")
    retry_policy: Dict[str, Any] = Field(
        default_factory=lambda: {"max_retries": 3, "backoff_multiplier": 2.0},
        description="Retry policy for tool calls"
    )


class ToolCall(BaseModel):
    """A call to a tool."""
    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    call_id: str = Field(..., description="Unique call ID")
    tenant_id: str = Field(..., description="Tenant ID")
    agent_type: str = Field(..., description="Type of agent making the call")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")
    timestamp: datetime = Field(..., description="When the call was made")


class ToolResult(BaseModel):
    """Result of a tool call."""
    call_id: str = Field(..., description="Reference to the ToolCall")
    status: str = Field(..., description="Status: success, error, timeout")
    result: Optional[Any] = Field(default=None, description="Tool result on success")
    error: Optional[str] = Field(default=None, description="Error message on failure")
    duration_ms: int = Field(..., description="Duration of the call in milliseconds")
    timestamp: datetime = Field(..., description="When the result was returned")
    retry_count: int = Field(default=0, description="Number of retries attempted")


class ToolError(BaseModel):
    """Error from a tool call."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    retryable: bool = Field(default=False, description="Whether the error is retryable")


# ============================================================================
# Integration Categories
# ============================================================================

class IntegrationCategory(str, Enum):
    CARRIER = "carrier"
    TMS = "tms"
    WMS = "wms"
    ERP = "erp"
    TELEMATICS = "telematics"
    MAPS = "maps"
    SIP = "sip"
    PAYMENT = "payment"
    NOTIFICATION = "notification"


# ============================================================================
# Pre-defined Tool Definitions
# ============================================================================

# Carrier Integration Tools
CARRIER_TOOLS = [
    ToolDefinition(
        name="carrier.get_tracking_info",
        description="Get tracking information for a shipment from a carrier",
        parameters=[
            ToolParameter(name="tracking_number", type="string", description="Carrier tracking number", required=True),
            ToolParameter(name="carrier", type="string", description="Carrier name", required=True),
        ],
        returns="Shipment tracking information including current status, location, and events",
        integration_type="carrier",
        category="tracking",
        tags=["tracking", "shipment", "status"],
        timeout_seconds=10,
    ),
    ToolDefinition(
        name="carrier.create_shipment",
        description="Create a new shipment with a carrier",
        parameters=[
            ToolParameter(name="origin", type="object", description="Origin address", required=True),
            ToolParameter(name="destination", type="object", description="Destination address", required=True),
            ToolParameter(name="weight_lbs", type="number", description="Weight in pounds", required=True),
            ToolParameter(name="service_level", type="string", description="Service level", required=False),
            ToolParameter(name="reference", type="string", description="Reference number", required=False),
        ],
        returns="Created shipment information including tracking number",
        integration_type="carrier",
        category="shipment",
        tags=["shipment", "create"],
        timeout_seconds=15,
    ),
    ToolDefinition(
        name="carrier.get_quote",
        description="Get a shipping quote from a carrier",
        parameters=[
            ToolParameter(name="origin", type="object", description="Origin address", required=True),
            ToolParameter(name="destination", type="object", description="Destination address", required=True),
            ToolParameter(name="weight_lbs", type="number", description="Weight in pounds", required=True),
            ToolParameter(name="service_level", type="string", description="Service level", required=False),
        ],
        returns="Shipping quote including cost and transit time",
        integration_type="carrier",
        category="quote",
        tags=["quote", "pricing"],
        timeout_seconds=10,
    ),
]

# TMS Integration Tools
TMS_TOOLS = [
    ToolDefinition(
        name="tms.get_order",
        description="Get order information from TMS",
        parameters=[
            ToolParameter(name="order_id", type="string", description="Order ID", required=True),
        ],
        returns="Order information including items, quantities, and status",
        integration_type="tms",
        category="order",
        tags=["order", "tms"],
        timeout_seconds=5,
    ),
    ToolDefinition(
        name="tms.update_order_status",
        description="Update order status in TMS",
        parameters=[
            ToolParameter(name="order_id", type="string", description="Order ID", required=True),
            ToolParameter(name="status", type="string", description="New status", required=True),
        ],
        returns="Updated order information",
        integration_type="tms",
        category="order",
        tags=["order", "status", "update"],
        timeout_seconds=5,
    ),
]

# Telematics Integration Tools
TELEMATICS_TOOLS = [
    ToolDefinition(
        name="telematics.get_vehicle_location",
        description="Get current location of a vehicle",
        parameters=[
            ToolParameter(name="vehicle_id", type="string", description="Vehicle ID", required=True),
        ],
        returns="Current location (lat, lng) and timestamp",
        integration_type="telematics",
        category="location",
        tags=["vehicle", "location", "gps"],
        timeout_seconds=5,
    ),
    ToolDefinition(
        name="telematics.get_vehicle_status",
        description="Get status of a vehicle (speed, engine hours, etc.)",
        parameters=[
            ToolParameter(name="vehicle_id", type="string", description="Vehicle ID", required=True),
        ],
        returns="Vehicle status information",
        integration_type="telematics",
        category="status",
        tags=["vehicle", "status", "telematics"],
        timeout_seconds=5,
    ),
    ToolDefinition(
        name="telematics.get_driver_hos",
        description="Get HOS (Hours of Service) information for a driver",
        parameters=[
            ToolParameter(name="driver_id", type="string", description="Driver ID", required=True),
        ],
        returns="HOS information including remaining hours",
        integration_type="telematics",
        category="hos",
        tags=["driver", "hos", "compliance"],
        timeout_seconds=5,
    ),
]

# Maps Integration Tools
MAPS_TOOLS = [
    ToolDefinition(
        name="maps.get_distance_matrix",
        description="Get distance and time between multiple locations",
        parameters=[
            ToolParameter(name="origins", type="array", description="List of origin locations", required=True),
            ToolParameter(name="destinations", type="array", description="List of destination locations", required=True),
            ToolParameter(name="mode", type="string", description="Travel mode (driving, walking, etc.)", required=False, default="driving"),
        ],
        returns="Distance matrix with distances and durations",
        integration_type="maps",
        category="routing",
        tags=["distance", "time", "routing"],
        timeout_seconds=10,
    ),
    ToolDefinition(
        name="maps.get_directions",
        description="Get directions between two points",
        parameters=[
            ToolParameter(name="origin", type="object", description="Origin location", required=True),
            ToolParameter(name="destination", type="object", description="Destination location", required=True),
            ToolParameter(name="waypoints", type="array", description="Waypoints along the route", required=False),
            ToolParameter(name="avoid", type="string", description="Avoid (tolls, highways, etc.)", required=False),
        ],
        returns="Directions including polyline and turn-by-turn instructions",
        integration_type="maps",
        category="routing",
        tags=["directions", "route", "navigation"],
        timeout_seconds=10,
    ),
    ToolDefinition(
        name="maps.geocode",
        description="Convert address to coordinates",
        parameters=[
            ToolParameter(name="address", type="string", description="Address to geocode", required=True),
        ],
        returns="Coordinates (lat, lng) and formatted address",
        integration_type="maps",
        category="geocoding",
        tags=["address", "geocode", "coordinates"],
        timeout_seconds=5,
    ),
    ToolDefinition(
        name="maps.get_traffic",
        description="Get traffic information for a route",
        parameters=[
            ToolParameter(name="route", type="object", description="Route definition", required=True),
        ],
        returns="Traffic information including delays and alternative routes",
        integration_type="maps",
        category="traffic",
        tags=["traffic", "delay", "routing"],
        timeout_seconds=10,
    ),
]

# SIP/Telephony Integration Tools
SIP_TOOLS = [
    ToolDefinition(
        name="sip.make_call",
        description="Make an outbound phone call",
        parameters=[
            ToolParameter(name="phone_number", type="string", description="Phone number to call", required=True),
            ToolParameter(name="caller_id", type="string", description="Caller ID to display", required=False),
            ToolParameter(name="message", type="string", description="Optional message to speak", required=False),
        ],
        returns="Call information including call ID and status",
        integration_type="sip",
        category="call",
        tags=["voice", "call", "outbound"],
        timeout_seconds=30,
    ),
    ToolDefinition(
        name="sip.transfer_call",
        description="Transfer a call to another number or extension",
        parameters=[
            ToolParameter(name="call_id", type="string", description="Call ID", required=True),
            ToolParameter(name="destination", type="string", description="Destination number or extension", required=True),
        ],
        returns="Transfer status",
        integration_type="sip",
        category="call",
        tags=["voice", "call", "transfer"],
        timeout_seconds=10,
    ),
    ToolDefinition(
        name="sip.end_call",
        description="End an active call",
        parameters=[
            ToolParameter(name="call_id", type="string", description="Call ID", required=True),
        ],
        returns="Call end status",
        integration_type="sip",
        category="call",
        tags=["voice", "call", "end"],
        timeout_seconds=5,
    ),
    ToolDefinition(
        name="sip.get_call_status",
        description="Get status of an active call",
        parameters=[
            ToolParameter(name="call_id", type="string", description="Call ID", required=True),
        ],
        returns="Call status information",
        integration_type="sip",
        category="call",
        tags=["voice", "call", "status"],
        timeout_seconds=5,
    ),
]

# Notification Integration Tools
NOTIFICATION_TOOLS = [
    ToolDefinition(
        name="notification.send_email",
        description="Send an email notification",
        parameters=[
            ToolParameter(name="to", type="string", description="Recipient email address", required=True),
            ToolParameter(name="subject", type="string", description="Email subject", required=True),
            ToolParameter(name="body", type="string", description="Email body", required=True),
            ToolParameter(name="template_id", type="string", description="Template ID", required=False),
        ],
        returns="Email send status",
        integration_type="notification",
        category="email",
        tags=["email", "notification"],
        timeout_seconds=10,
    ),
    ToolDefinition(
        name="notification.send_sms",
        description="Send an SMS notification",
        parameters=[
            ToolParameter(name="to", type="string", description="Recipient phone number", required=True),
            ToolParameter(name="message", type="string", description="SMS message", required=True),
        ],
        returns="SMS send status",
        integration_type="notification",
        category="sms",
        tags=["sms", "notification"],
        timeout_seconds=10,
    ),
]

# All available tools
ALL_TOOLS = CARRIER_TOOLS + TMS_TOOLS + TELEMATICS_TOOLS + MAPS_TOOLS + SIP_TOOLS + NOTIFICATION_TOOLS

# Tool registry by integration type
TOOL_REGISTRY = {
    "carrier": CARRIER_TOOLS,
    "tms": TMS_TOOLS,
    "telematics": TELEMATICS_TOOLS,
    "maps": MAPS_TOOLS,
    "sip": SIP_TOOLS,
    "notification": NOTIFICATION_TOOLS,
}
