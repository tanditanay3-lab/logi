"""
Schemas for the Shipment Tracking Agent.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.shared_types.schemas import AgentType, TrustLevel


class ShipmentStatus(str, Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    DELAYED = "delayed"


class Location(BaseModel):
    """Location model."""
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class ShipmentEvent(BaseModel):
    """Shipment event model."""
    id: str
    timestamp: datetime
    event_type: str
    description: str
    location: Optional[Location] = None
    carrier_timestamp: Optional[datetime] = None


class ShipmentEventCreate(BaseModel):
    """Create shipment event request."""
    timestamp: datetime
    event_type: str = Field(..., description="Type of tracking event")
    description: str = Field(..., description="Description of the event")
    location: Optional[Location] = None
    carrier_timestamp: Optional[datetime] = None


class ShipmentMetadata(BaseModel):
    """Shipment metadata."""
    weight_lbs: Optional[float] = None
    dimensions: Optional[Dict[str, float]] = None
    commodity: Optional[str] = None
    reference_numbers: Optional[List[str]] = None


class ShipmentBase(BaseModel):
    """Base shipment model."""
    tracking_number: str = Field(..., description="Carrier tracking number")
    carrier: str = Field(..., description="Carrier name")
    carrier_service: Optional[str] = Field(default=None, description="Carrier service level")
    status: ShipmentStatus = Field(default=ShipmentStatus.PENDING)
    origin: Location = Field(..., description="Origin location")
    destination: Location = Field(..., description="Destination location")
    estimated_delivery: Optional[datetime] = Field(default=None, description="Estimated delivery time")
    metadata: ShipmentMetadata = Field(default_factory=ShipmentMetadata)
    notes: Optional[str] = Field(default=None, description="Additional notes")


class ShipmentCreate(ShipmentBase):
    """Create shipment request."""
    pass


class Shipment(ShipmentBase):
    """Full shipment model."""
    id: str
    tenant_id: str
    current_location: Optional[Location] = None
    actual_delivery: Optional[datetime] = None
    eta_drift_minutes: Optional[float] = None
    eta_drift_detected_at: Optional[datetime] = None
    carrier_account: Optional[str] = None
    billing_reference: Optional[str] = None
    events: List[ShipmentEvent] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ShipmentUpdate(BaseModel):
    """Update shipment request."""
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    carrier_service: Optional[str] = None
    status: Optional[ShipmentStatus] = None
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    current_location: Optional[Location] = None
    metadata: Optional[ShipmentMetadata] = None
    notes: Optional[str] = None


class ShipmentListResponse(BaseModel):
    """List shipments response."""
    shipments: List[Shipment]
    total: int
    limit: int
    offset: int


class TrackingRefreshResponse(BaseModel):
    """Tracking refresh response."""
    status: str = Field(..., description="Status of the refresh")
    shipment_id: str = Field(..., description="ID of the shipment being refreshed")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")


class NotificationRequest(BaseModel):
    """Notification request."""
    message_template: Optional[str] = Field(default=None, description="Message template to use")
    channels: List[str] = Field(default_factory=list, description="Channels to send notification")
    recipient: Dict[str, str] = Field(default_factory=dict, description="Recipient information")


class NotificationResponse(BaseModel):
    """Notification response."""
    status: str = Field(..., description="Status of the notification")
    notification_id: str = Field(..., description="ID of the notification")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")


class TrackingWebhookPayload(BaseModel):
    """Carrier webhook payload."""
    tracking_number: str = Field(..., description="Tracking number")
    carrier: str = Field(..., description="Carrier name")
    event_type: str = Field(..., description="Event type")
    event_description: str = Field(..., description="Event description")
    event_timestamp: datetime = Field(..., description="When the event occurred")
    location: Optional[Location] = None
    status: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    signature: Optional[str] = Field(default=None, description="Carrier signature for verification")


class TrackingWebhookResponse(BaseModel):
    """Tracking webhook response."""
    status: str = Field(..., description="Status of the webhook processing")
    shipment_id: Optional[str] = Field(default=None, description="ID of the created/updated shipment")
    tracking_number: Optional[str] = Field(default=None, description="Tracking number")
    events_created: int = Field(default=0, description="Number of events created")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")


class EtaDriftDetection(BaseModel):
    """ETA drift detection result."""
    shipment_id: str
    tracking_number: str
    original_eta: datetime
    current_eta: datetime
    drift_minutes: float
    drift_detected: bool
    threshold_minutes: float = 30.0


class ShipmentStats(BaseModel):
    """Shipment statistics."""
    total_shipments: int
    in_transit: int
    delivered: int
    delayed: int
    cancelled: int
    pending: int
    avg_delivery_time_hours: float
    on_time_delivery_rate: float
