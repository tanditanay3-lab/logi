"""
Core schemas for Lanework shared types.

All agents use these common schemas for AgentTask, Conversation, Config, etc.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class AgentType(str, Enum):
    """Types of agents in the Lanework system."""
    SHIPMENT_TRACKING = "shipment-tracking"
    INVENTORY = "inventory"
    ROUTE_OPTIMIZATION = "route-optimization"
    WAREHOUSE_OPS = "warehouse-ops"
    FLEET_MANAGEMENT = "fleet-management"
    CUSTOMER_COMMUNICATION = "customer-communication"
    DEMAND_FORECASTING = "demand-forecasting"
    FREIGHT_PROCUREMENT = "freight-procurement"
    VOICE = "voice"


class AgentTaskStatus(str, Enum):
    """Status of an AgentTask."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_EXECUTED = "auto_executed"
    FAILED = "failed"
    COMPLETED = "completed"


class TrustLevel(str, Enum):
    """Trust levels for agent actions."""
    PROPOSE_ONLY = "propose_only"
    AUTO_EXECUTE_LOW_RISK = "auto_execute_low_risk"
    FULLY_AUTONOMOUS = "fully_autonomous"


class ApprovalRequestStatus(str, Enum):
    """Status of an ApprovalRequest."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ConversationChannel(str, Enum):
    """Channel for conversations."""
    CHAT = "chat"
    VOICE = "voice"


class VoiceCallDirection(str, Enum):
    """Direction of a voice call."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class VoiceCallerType(str, Enum):
    """Type of caller for voice calls."""
    DRIVER = "driver"
    CUSTOMER = "customer"
    DISPATCHER = "dispatcher"
    UNKNOWN = "unknown"


class WebhookEventType(str, Enum):
    """Types of webhook events."""
    # Shipment Tracking
    SHIPMENT_CREATED = "shipment.created"
    SHIPMENT_UPDATED = "shipment.updated"
    SHIPMENT_STATUS_CHANGED = "shipment.status_changed"
    SHIPMENT_ETA_DRIFT_DETECTED = "shipment.eta_drift_detected"
    SHIPMENT_DELIVERED = "shipment.delivered"
    SHIPMENT_DELAYED = "shipment.delayed"
    
    # Inventory
    INVENTORY_ITEM_CREATED = "inventory.item.created"
    INVENTORY_ITEM_UPDATED = "inventory.item.updated"
    INVENTORY_QUANTITY_ADJUSTED = "inventory.quantity_adjusted"
    INVENTORY_RESERVED = "inventory.reserved"
    INVENTORY_RELEASED = "inventory.released"
    INVENTORY_LOW_STOCK = "inventory.low_stock"
    INVENTORY_DISCREPANCY_REPORTED = "inventory.discrepancy_reported"
    INVENTORY_REPLENISHMENT_RECOMMENDED = "inventory.replenishment_recommended"
    
    # Route Optimization
    ROUTE_CREATED = "route.created"
    ROUTE_OPTIMIZED = "route.optimized"
    ROUTE_REOPTIMIZED = "route.reoptimized"
    ROUTE_ASSIGNED = "route.assigned"
    ROUTE_STARTED = "route.started"
    ROUTE_COMPLETED = "route.completed"
    ROUTE_STOP_STARTED = "route.stop.started"
    ROUTE_STOP_COMPLETED = "route.stop.completed"
    ROUTE_STOP_SKIPPED = "route.stop.skipped"
    
    # Warehouse Operations
    WAREHOUSE_TASK_CREATED = "warehouse.task.created"
    WAREHOUSE_TASK_ASSIGNED = "warehouse.task.assigned"
    WAREHOUSE_TASK_COMPLETED = "warehouse.task.completed"
    WAREHOUSE_TASKS_OPTIMIZED = "warehouse.tasks.optimized"
    WAREHOUSE_DOCK_SCHEDULE_UPDATED = "warehouse.dock_schedule.updated"
    WAREHOUSE_LABOR_FORECAST_GENERATED = "warehouse.labor_forecast.generated"
    
    # Fleet Management
    FLEET_DRIVER_HOS_UPDATED = "fleet.driver.hos_updated"
    FLEET_DRIVER_ASSIGNED = "fleet.driver.assigned"
    FLEET_VEHICLE_MAINTENANCE_LOGGED = "fleet.vehicle.maintenance_logged"
    FLEET_VEHICLE_ASSIGNED = "fleet.vehicle.assigned"
    FLEET_COMPLIANCE_ALERT = "fleet.compliance.alert"
    FLEET_HOS_VIOLATION = "fleet.hos.violation"
    
    # Customer Communication
    CUSTOMER_CONVERSATION_CREATED = "customer.conversation.created"
    CUSTOMER_CONVERSATION_CLOSED = "customer.conversation.closed"
    CUSTOMER_CONVERSATION_ESCALATED = "customer.conversation.escalated"
    CUSTOMER_NOTIFICATION_SENT = "customer.notification.sent"
    CUSTOMER_SENTIMENT_NEGATIVE_DETECTED = "customer.sentiment.negative_detected"
    
    # Demand Forecasting
    FORECAST_GENERATED = "forecast.generated"
    FORECAST_RETRAINED = "forecast.retrained"
    FORECAST_INSIGHTS_GENERATED = "forecast.insights_generated"
    
    # Freight Procurement
    FREIGHT_QUOTE_REQUESTED = "freight.quote.requested"
    FREIGHT_QUOTE_RECEIVED = "freight.quote.received"
    FREIGHT_QUOTE_SELECTED = "freight.quote.selected"
    FREIGHT_CARRIER_CREATED = "freight.carrier.created"
    FREIGHT_CARRIER_PERFORMANCE_UPDATED = "freight.carrier.performance_updated"
    
    # Voice
    VOICE_CALL_STARTED = "voice.call.started"
    VOICE_CALL_COMPLETED = "voice.call.completed"
    VOICE_CALL_ESCALATED = "voice.call.escalated"


# ============================================================================
# AgentTask
# ============================================================================

class AgentTaskBase(BaseModel):
    """Base schema for AgentTask."""
    agent_type: AgentType
    action_type: str = Field(..., description="Type of action being performed")
    trust_level: TrustLevel = Field(default=TrustLevel.PROPOSE_ONLY)
    reasoning_trace: str = Field(..., description="Full LLM reasoning trace for audit")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Structured input that triggered this task")
    output_data: Optional[Dict[str, Any]] = Field(default=None, description="Result of the action if executed")
    related_entity_id: Optional[str] = Field(default=None, description="ID of related entity (shipment_id, route_id, etc.)")
    related_entity_type: Optional[str] = Field(default=None, description="Type of related entity")
    error_message: Optional[str] = Field(default=None, description="Error message if task failed")


class AgentTaskCreate(AgentTaskBase):
    """Schema for creating an AgentTask."""
    tenant_id: str = Field(..., description="Tenant ID")
    status: AgentTaskStatus = Field(default=AgentTaskStatus.PENDING_APPROVAL)
    approval_request_id: Optional[str] = Field(default=None)


class AgentTask(AgentTaskBase):
    """Full AgentTask schema with all fields."""
    id: str = Field(..., description="Unique task ID")
    tenant_id: str = Field(..., description="Tenant ID")
    status: AgentTaskStatus = Field(..., description="Current status of the task")
    approval_request_id: Optional[str] = Field(default=None, description="Reference to ApprovalRequest if pending approval")
    created_at: datetime = Field(..., description="When the task was created")
    updated_at: datetime = Field(..., description="When the task was last updated")
    completed_at: Optional[datetime] = Field(default=None, description="When the task was completed")

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class AgentTaskUpdate(BaseModel):
    """Schema for updating an AgentTask."""
    status: Optional[AgentTaskStatus] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    approval_request_id: Optional[str] = None


# ============================================================================
# ApprovalRequest
# ============================================================================

class ApprovalRequestBase(BaseModel):
    """Base schema for ApprovalRequest."""
    agent_task_id: str = Field(..., description="Reference to the AgentTask")
    agent_type: AgentType = Field(..., description="Type of agent that created the task")
    action_description: str = Field(..., description="Human-readable summary of what needs approval")
    requested_by: str = Field(..., description="User ID or 'system'")


class ApprovalRequestCreate(ApprovalRequestBase):
    """Schema for creating an ApprovalRequest."""
    tenant_id: str = Field(..., description="Tenant ID")
    status: ApprovalRequestStatus = Field(default=ApprovalRequestStatus.PENDING)
    expires_at: Optional[datetime] = Field(default=None)


class ApprovalRequest(ApprovalRequestBase):
    """Full ApprovalRequest schema."""
    id: str = Field(..., description="Unique approval request ID")
    tenant_id: str = Field(..., description="Tenant ID")
    status: ApprovalRequestStatus = Field(..., description="Current status")
    approved_by: Optional[str] = Field(default=None, description="User ID who approved")
    rejected_by: Optional[str] = Field(default=None, description="User ID who rejected")
    rejection_reason: Optional[str] = Field(default=None, description="Reason for rejection")
    created_at: datetime = Field(..., description="When the request was created")
    updated_at: datetime = Field(..., description="When the request was last updated")


# ============================================================================
# Conversation
# ============================================================================

class ConversationMessage(BaseModel):
    """A single message in a conversation."""
    id: str = Field(..., description="Unique message ID")
    role: str = Field(..., description="Role: user, assistant, system")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="When the message was sent")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ConversationBase(BaseModel):
    """Base schema for Conversation."""
    tenant_id: str = Field(..., description="Tenant ID")
    channel: ConversationChannel = Field(..., description="Channel: chat or voice")
    participant_type: str = Field(..., description="Type of participant: user, driver, customer, system")
    participant_id: Optional[str] = Field(default=None, description="ID of the participant")
    messages: List[ConversationMessage] = Field(default_factory=list, description="List of messages")
    related_agent_task_ids: List[str] = Field(default_factory=list, description="Related AgentTask IDs")
    voice_call_id: Optional[str] = Field(default=None, description="Reference to VoiceCall if voice channel")


class ConversationCreate(ConversationBase):
    """Schema for creating a Conversation."""
    pass


class Conversation(ConversationBase):
    """Full Conversation schema."""
    id: str = Field(..., description="Unique conversation ID")
    created_at: datetime = Field(..., description="When the conversation was created")
    updated_at: datetime = Field(..., description="When the conversation was last updated")


class ConversationUpdate(BaseModel):
    """Schema for updating a Conversation."""
    messages: Optional[List[ConversationMessage]] = None
    related_agent_task_ids: Optional[List[str]] = None
    voice_call_id: Optional[str] = None


# ============================================================================
# Config
# ============================================================================

class AutoApprovalThresholds(BaseModel):
    """Thresholds for auto-approval."""
    max_monetary_value: float = Field(default=1000.00, description="Maximum monetary value for auto-approval")
    max_route_deviation_minutes: int = Field(default=30, description="Maximum route deviation for auto-approval")
    max_inventory_adjustment_pct: float = Field(default=5.0, description="Maximum inventory adjustment percentage for auto-approval")


class NotificationSettings(BaseModel):
    """Notification settings."""
    email_enabled: bool = Field(default=True)
    sms_enabled: bool = Field(default=True)
    voice_enabled: bool = Field(default=False)
    webhook_url: Optional[str] = Field(default=None)


class IntegrationSettings(BaseModel):
    """Integration settings."""
    carrier_webhook_enabled: bool = Field(default=True)
    tms_sync_enabled: bool = Field(default=False)
    telematics_enabled: bool = Field(default=False)


class Config(BaseModel):
    """Configuration for an agent."""
    trust_level: TrustLevel = Field(default=TrustLevel.PROPOSE_ONLY)
    auto_approval_thresholds: AutoApprovalThresholds = Field(default_factory=AutoApprovalThresholds)
    notification_settings: NotificationSettings = Field(default_factory=NotificationSettings)
    integration_settings: IntegrationSettings = Field(default_factory=IntegrationSettings)
    agent_specific: Optional[Dict[str, Any]] = Field(default=None, description="Agent-specific configuration")


# ============================================================================
# VoiceCall
# ============================================================================

class StructuredIntent(BaseModel):
    """Structured intent extracted from voice call."""
    agent_routed_to: Optional[AgentType] = Field(default=None)
    extracted_request: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class VoiceCallBase(BaseModel):
    """Base schema for VoiceCall."""
    tenant_id: str = Field(..., description="Tenant ID")
    direction: VoiceCallDirection = Field(..., description="Call direction")
    caller_type: VoiceCallerType = Field(default=VoiceCallerType.UNKNOWN)
    phone_number: str = Field(..., description="Phone number")
    transcript: Optional[str] = Field(default=None, description="Full transcript")
    structured_intent: Optional[StructuredIntent] = Field(default=None)
    duration_seconds: Optional[int] = Field(default=None, description="Call duration in seconds")
    escalated_to_human: bool = Field(default=False)
    recording_url: Optional[str] = Field(default=None, description="URL to call recording")
    related_agent_task_ids: List[str] = Field(default_factory=list, description="Related AgentTask IDs")


class VoiceCallCreate(VoiceCallBase):
    """Schema for creating a VoiceCall."""
    pass


class VoiceCall(VoiceCallBase):
    """Full VoiceCall schema."""
    id: str = Field(..., description="Unique call ID")
    timestamp: datetime = Field(..., description="When the call started")
    ended_at: Optional[datetime] = Field(default=None, description="When the call ended")


# ============================================================================
# WebhookEvent
# ============================================================================

class WebhookEvent(BaseModel):
    """Webhook event schema."""
    event_id: str = Field(..., description="Unique event ID")
    event_type: WebhookEventType = Field(..., description="Type of event")
    tenant_id: str = Field(..., description="Tenant ID")
    timestamp: datetime = Field(..., description="When the event occurred")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific payload")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")
