"""
Pydantic schemas for the Customer Communication Agent.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class ConversationStatus(str, Enum):
    """Status of a customer conversation."""
    OPEN = "open"
    CLOSED = "closed"
    ESCALATED = "escalated"


class ConversationChannel(str, Enum):
    """Channel for customer conversations."""
    CHAT = "chat"
    EMAIL = "email"
    VOICE = "voice"


class MessageRole(str, Enum):
    """Role of a message participant."""
    CUSTOMER = "customer"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Sentiment(str, Enum):
    """Sentiment of a message."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ConversationPriority(str, Enum):
    """Priority of a conversation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """Type of customer notification."""
    DELAY = "delay"
    DELIVERY_CONFIRMATION = "delivery_confirmation"
    PICKUP_CONFIRMATION = "pickup_confirmation"
    EXCEPTION = "exception"


class NotificationStatus(str, Enum):
    """Status of a notification."""
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


# ============================================================================
# Message Schema
# ============================================================================

class Message(BaseModel):
    """Schema for a message in a conversation."""
    id: str = Field(..., description="Unique message ID")
    role: MessageRole = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="When the message was sent")
    sentiment: Optional[Sentiment] = Field(default=None, description="Sentiment analysis result")
    intent: Optional[str] = Field(default=None, description="Extracted intent")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


# ============================================================================
# Conversation Schemas
# ============================================================================

class ConversationBase(BaseModel):
    """Base schema for customer conversations."""
    customer_id: str = Field(..., description="Customer ID")
    channel: ConversationChannel = Field(..., description="Conversation channel")
    subject: str = Field(..., description="Conversation subject")
    messages: List[Message] = Field(default_factory=list, description="List of messages")
    assigned_to: Optional[str] = Field(default=None, description="User ID assigned to this conversation")
    priority: ConversationPriority = Field(default=ConversationPriority.MEDIUM)
    related_shipment_ids: List[str] = Field(default_factory=list, description="Related shipment IDs")


class ConversationCreate(ConversationBase):
    """Schema for creating a customer conversation."""
    pass


class Conversation(ConversationBase):
    """Full schema for customer conversations."""
    id: str = Field(..., description="Unique conversation ID")
    tenant_id: str = Field(..., description="Tenant ID")
    status: ConversationStatus = Field(default=ConversationStatus.OPEN)
    created_at: datetime = Field(..., description="When the conversation was created")
    updated_at: datetime = Field(..., description="When the conversation was last updated")
    closed_at: Optional[datetime] = Field(default=None, description="When the conversation was closed")

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v):
        if isinstance(v, str) and v.startswith('conv_'):
            return v
        return f"conv_{v}" if isinstance(v, str) else v


class ConversationListResponse(BaseModel):
    """Response for listing customer conversations."""
    conversations: List[Conversation] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""
    status: Optional[ConversationStatus] = None
    assigned_to: Optional[str] = None
    priority: Optional[ConversationPriority] = None
    subject: Optional[str] = None


# ============================================================================
# Reply Schema
# ============================================================================

class ReplyRequest(BaseModel):
    """Request to send a reply to a conversation."""
    content: str = Field(..., description="Reply content")
    channel: ConversationChannel = Field(..., description="Channel to send the reply")
    template_id: Optional[str] = Field(default=None, description="Template ID to use")


class ReplyResponse(BaseModel):
    """Response for sending a reply."""
    conversation_id: str = Field(..., description="Conversation ID")
    message_id: str = Field(..., description="Message ID")
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this reply")


# ============================================================================
# Escalation Schema
# ============================================================================

class EscalationRequest(BaseModel):
    """Request to escalate a conversation."""
    reason: str = Field(..., description="Reason for escalation")
    priority: ConversationPriority = Field(default=ConversationPriority.MEDIUM)
    assign_to: Optional[str] = Field(default=None, description="User ID to assign to")


class EscalationResponse(BaseModel):
    """Response for escalating a conversation."""
    conversation_id: str = Field(..., description="Conversation ID")
    escalation_id: str = Field(..., description="Escalation ID")
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this escalation")


# ============================================================================
# Notification Schemas
# ============================================================================

class NotificationRequest(BaseModel):
    """Request to send a proactive notification."""
    customer_id: str = Field(..., description="Customer ID")
    shipment_id: Optional[str] = Field(default=None, description="Related shipment ID")
    notification_type: NotificationType = Field(..., description="Type of notification")
    message: str = Field(..., description="Notification message")
    channels: List[str] = Field(default_factory=list, description="Channels to send notification")
    template_id: Optional[str] = Field(default=None, description="Template ID to use")


class NotificationResponse(BaseModel):
    """Response for sending a notification."""
    notification_id: str = Field(..., description="Notification ID")
    status: NotificationStatus = Field(..., description="Notification status")
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this notification")


# ============================================================================
# Sentiment Analysis Schema
# ============================================================================

class SentimentAnalysisRequest(BaseModel):
    """Request to analyze sentiment of a message."""
    message: str = Field(..., description="Message to analyze")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")


class SentimentAnalysisResponse(BaseModel):
    """Response for sentiment analysis."""
    sentiment: Sentiment = Field(..., description="Detected sentiment")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    intent: Optional[str] = Field(default=None, description="Extracted intent")
    agent_task_id: Optional[str] = Field(default=None, description="AgentTask ID for this analysis")


# ============================================================================
# Stats Schemas
# ============================================================================

class CustomerSupportStats(BaseModel):
    """Statistics for customer support."""
    total_conversations: int = Field(default=0)
    open_conversations: int = Field(default=0)
    closed_conversations: int = Field(default=0)
    escalated_conversations: int = Field(default=0)
    avg_response_time_minutes: float = Field(default=0.0)
    avg_resolution_time_minutes: float = Field(default=0.0)
    customer_satisfaction_score: float = Field(default=0.0)
    notifications_sent: int = Field(default=0)
    negative_sentiment_count: int = Field(default=0)
