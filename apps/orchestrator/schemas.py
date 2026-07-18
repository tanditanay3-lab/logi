"""
Schemas for the Orchestrator.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from packages.shared_types.schemas import (
    AgentType,
    AgentTask as AgentTaskSchema,
    AgentTaskStatus,
    ApprovalRequest,
    ApprovalRequestStatus,
    Conversation as ConversationSchema,
    ConversationChannel,
    ConversationMessage,
    TrustLevel,
)


class IntentType(str, Enum):
    """Types of intents that can be extracted from conversations."""
    STATUS_QUERY = "status_query"
    TRACKING_REQUEST = "tracking_request"
    ROUTE_OPTIMIZATION = "route_optimization"
    INVENTORY_CHECK = "inventory_check"
    DRIVER_ISSUE = "driver_issue"
    CUSTOMER_COMPLAINT = "customer_complaint"
    GENERAL_QUESTION = "general_question"
    UNKNOWN = "unknown"


class ConversationRequest(BaseModel):
    """Request to the Conversation Router."""
    tenant_id: str = Field(..., description="Tenant ID")
    conversation_id: Optional[str] = Field(default=None, description="Existing conversation ID")
    message: str = Field(..., description="User message")
    channel: ConversationChannel = Field(default=ConversationChannel.CHAT)
    participant_type: str = Field(default="user")
    participant_id: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StructuredIntent(BaseModel):
    """Structured intent extracted from a conversation."""
    intent_type: IntentType = Field(..., description="Type of intent")
    agent_type: Optional[AgentType] = Field(default=None, description="Agent to route to")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    action: Optional[str] = Field(default=None, description="Specific action to perform")


class ConversationResponse(BaseModel):
    """Response from the Conversation Router."""
    conversation_id: str = Field(..., description="Conversation ID")
    message_id: str = Field(..., description="Message ID")
    response: str = Field(..., description="Agent response")
    structured_intent: Optional[StructuredIntent] = Field(default=None)
    agent_type: Optional[AgentType] = Field(default=None, description="Agent that handled the request")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")
    requires_approval: bool = Field(default=False)
    approval_request_id: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PlanRequest(BaseModel):
    """Request to the Planner."""
    tenant_id: str = Field(..., description="Tenant ID")
    goal: str = Field(..., description="Goal to achieve")
    constraints: List[str] = Field(default_factory=list, description="Constraints")
    available_agents: List[AgentType] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """A single step in a plan."""
    step_id: str = Field(..., description="Step ID")
    agent_type: AgentType = Field(..., description="Agent to execute this step")
    action: str = Field(..., description="Action to perform")
    description: str = Field(..., description="Human-readable description")
    dependencies: List[str] = Field(default_factory=list, description="Step dependencies")
    estimated_duration_seconds: float = Field(default=0.0)
    trust_level_required: TrustLevel = Field(default=TrustLevel.PROPOSE_ONLY)


class PlanResponse(BaseModel):
    """Response from the Planner."""
    plan_id: str = Field(..., description="Plan ID")
    goal: str = Field(..., description="Goal of the plan")
    steps: List[PlanStep] = Field(default_factory=list, description="Plan steps")
    estimated_total_duration_seconds: float = Field(default=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskRequest(BaseModel):
    """Request to execute a task."""
    tenant_id: str = Field(..., description="Tenant ID")
    agent_type: AgentType = Field(..., description="Agent type")
    action_type: str = Field(..., description="Action type")
    input_data: Dict[str, Any] = Field(default_factory=dict)
    trust_level: TrustLevel = Field(default=TrustLevel.PROPOSE_ONLY)
    context: Dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    """Response from task execution."""
    agent_task_id: str = Field(..., description="AgentTask ID")
    status: AgentTaskStatus = Field(..., description="Task status")
    output_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = Field(default=None)
    requires_approval: bool = Field(default=False)
    approval_request_id: Optional[str] = Field(default=None)


class AgentInfo(BaseModel):
    """Information about a registered agent."""
    agent_type: AgentType = Field(..., description="Agent type")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    endpoint: str = Field(..., description="Agent API endpoint")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")
    trust_level: TrustLevel = Field(default=TrustLevel.PROPOSE_ONLY)
    is_active: bool = Field(default=True)
    last_heartbeat: Optional[datetime] = Field(default=None)


class GuardrailsCheckRequest(BaseModel):
    """Request to check against guardrails."""
    tenant_id: str = Field(..., description="Tenant ID")
    agent_type: AgentType = Field(..., description="Agent type")
    action_type: str = Field(..., description="Action type")
    input_data: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class GuardrailsCheckResponse(BaseModel):
    """Response from guardrails check."""
    allowed: bool = Field(..., description="Whether the action is allowed")
    violations: List[str] = Field(default_factory=list, description="List of violations")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    required_trust_level: TrustLevel = Field(default=TrustLevel.PROPOSE_ONLY)
    recommended_action: Optional[str] = Field(default=None)


class WebhookEvent(BaseModel):
    """Webhook event for cross-agent communication."""
    event_id: str = Field(..., description="Event ID")
    event_type: str = Field(..., description="Event type")
    tenant_id: str = Field(..., description="Tenant ID")
    data: Dict[str, Any] = Field(default_factory=dict)
    source_agent: AgentType = Field(..., description="Source agent")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
