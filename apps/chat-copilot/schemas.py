"""
Schemas for the Chat Copilot.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.shared_types.schemas import (
    AgentType,
    Conversation as ConversationSchema,
    ConversationChannel,
)


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A single chat message."""
    id: str = Field(..., description="Message ID")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="When the message was sent")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ChatRequest(BaseModel):
    """Request to the Chat Copilot."""
    tenant_id: str = Field(..., description="Tenant ID")
    conversation_id: Optional[str] = Field(default=None, description="Existing conversation ID")
    message: str = Field(..., description="User message")
    participant_type: str = Field(default="user", description="Type of participant")
    participant_id: Optional[str] = Field(default=None, description="Participant ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ChatResponse(BaseModel):
    """Response from the Chat Copilot."""
    conversation_id: str = Field(..., description="Conversation ID")
    message_id: str = Field(..., description="Message ID")
    response: str = Field(..., description="Agent response")
    agent_type: Optional[AgentType] = Field(default=None, description="Agent that handled the request")
    agent_task_id: Optional[str] = Field(default=None, description="Reference to AgentTask")
    requires_approval: bool = Field(default=False, description="Whether approval is required")
    approval_request_id: Optional[str] = Field(default=None, description="Reference to ApprovalRequest")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    timestamp: datetime = Field(..., description="When the response was generated")
    structured_intent: Optional[Dict[str, Any]] = Field(default=None, description="Structured intent")


class ConversationSummary(BaseModel):
    """Summary of a conversation."""
    id: str = Field(..., description="Conversation ID")
    tenant_id: str = Field(..., description="Tenant ID")
    participant_type: str = Field(..., description="Participant type")
    participant_id: Optional[str] = Field(default=None, description="Participant ID")
    message_count: int = Field(..., description="Number of messages")
    last_message: Optional[str] = Field(default=None, description="Last message content")
    last_message_time: Optional[datetime] = Field(default=None, description="When the last message was sent")
    agent_types: List[AgentType] = Field(default_factory=list, description="Agents involved in conversation")
    status: str = Field(default="open", description="Conversation status")


class ConversationListResponse(BaseModel):
    """List conversations response."""
    conversations: List[ConversationSummary]
    total: int
    limit: int
    offset: int


class ChatStats(BaseModel):
    """Chat statistics."""
    total_conversations: int
    active_conversations: int
    messages_today: int
    avg_response_time_seconds: float
    agent_usage: Dict[str, int] = Field(default_factory=dict)
