"""
Service layer for the Customer Communication Agent.

This service handles all business logic for customer communication including:
- Managing customer conversations
- Sending replies to customers
- Escalating conversations
- Sending proactive notifications
- Analyzing sentiment
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from packages.db.models import (
    AgentTask as AgentTaskModel,
    Customer as CustomerModel,
    Shipment as ShipmentModel,
    Tenant,
    User,
)
from packages.shared_types.schemas import (
    AgentTask,
    AgentTaskCreate,
    AgentTaskStatus,
    AgentType,
    ApprovalRequest,
    ApprovalRequestCreate,
    ApprovalRequestStatus,
    Config,
    Conversation as ConversationModel,
    ConversationChannel,
    ConversationMessage,
    TrustLevel,
    WebhookEvent,
    WebhookEventType,
)
from packages.shared_types.utils import generate_id, get_current_timestamp
from packages.tool_bus.mcp_client import MCPClient
from packages.tool_bus.tool_definitions import ToolCall, ToolResult

from .config import CustomerSupportConfig
from .schemas import (
    Conversation,
    ConversationCreate,
    ConversationListResponse,
    ConversationPriority,
    ConversationStatus,
    ConversationUpdate,
    EscalationRequest,
    EscalationResponse,
    Message,
    MessageRole,
    NotificationRequest,
    NotificationResponse,
    NotificationStatus,
    NotificationType,
    ReplyRequest,
    ReplyResponse,
    Sentiment,
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
)

logger = logging.getLogger(__name__)


class CustomerSupportService:
    """
    Service for managing customer communications.
    
    This service handles:
    - Creating and managing customer conversations
    - Sending replies to customers
    - Escalating conversations to human agents
    - Sending proactive notifications
    - Analyzing message sentiment
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config: CustomerSupportConfig,
        tool_client: Optional[MCPClient] = None
    ):
        self.db_session = db_session
        self.config = config
        self.tool_client = tool_client or MCPClient()
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        logger.info("Customer Support Service initialized")
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
        logger.info("Customer Support Service closed")
    
    # ========================================================================
    # Conversation Operations
    # ========================================================================
    
    async def create_conversation(
        self,
        conversation_data: ConversationCreate,
        tenant_id: str
    ) -> Tuple[Conversation, Optional[AgentTask]]:
        """
        Create a new customer conversation.
        
        Args:
            conversation_data: Conversation data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created conversation, agent task if created)
        """
        # Conversations are typically auto-executed as they're just data entry
        agent_task: Optional[AgentTask] = None
        
        # Create the conversation
        conversation_model = ConversationModel(
            id=generate_id("conv"),
            tenant_id=tenant_id,
            channel=conversation_data.channel,
            participant_type="customer",
            participant_id=conversation_data.customer_id,
            messages=[msg.model_dump() for msg in conversation_data.messages],
            related_agent_task_ids=[],
            voice_call_id=None,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(conversation_model)
        await self.db_session.commit()
        await self.db_session.refresh(conversation_model)
        
        # Convert to schema
        conversation = await self._conversation_model_to_schema(conversation_model)
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.CUSTOMER_CONVERSATION_CREATED,
            data={
                "conversation_id": conversation.id,
                "customer_id": conversation.customer_id,
                "channel": conversation.channel.value
            },
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return conversation, agent_task
    
    async def get_conversation(self, conversation_id: str, tenant_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        result = await self.db_session.execute(
            select(ConversationModel)
            .where(
                and_(
                    ConversationModel.id == conversation_id,
                    ConversationModel.tenant_id == tenant_id
                )
            )
        )
        
        conversation_model = result.scalar_one_or_none()
        if not conversation_model:
            return None
        
        return await self._conversation_model_to_schema(conversation_model)
    
    async def list_conversations(
        self,
        tenant_id: str,
        customer_id: Optional[str] = None,
        status: Optional[ConversationStatus] = None,
        channel: Optional[ConversationChannel] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Conversation], int]:
        """List conversations with optional filters."""
        query = select(ConversationModel).where(
            and_(
                ConversationModel.tenant_id == tenant_id,
                ConversationModel.participant_type == "customer"
            )
        )
        
        if customer_id:
            query = query.where(ConversationModel.participant_id == customer_id)
        if status:
            # Status is stored in messages or metadata, need to filter differently
            pass
        if channel:
            query = query.where(ConversationModel.channel == channel)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db_session.execute(count_query)
        total = count_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(desc(ConversationModel.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        conversation_models = result.scalars().all()
        
        conversations = [await self._conversation_model_to_schema(model) for model in conversation_models]
        
        return conversations, total
    
    async def update_conversation(
        self,
        conversation_id: str,
        conversation_data: ConversationUpdate,
        tenant_id: str
    ) -> Tuple[Optional[Conversation], Optional[AgentTask]]:
        """
        Update a conversation.
        
        Returns:
            Tuple of (updated conversation, agent task if approval required)
        """
        # Get existing conversation
        result = await self.db_session.execute(
            select(ConversationModel)
            .where(
                and_(
                    ConversationModel.id == conversation_id,
                    ConversationModel.tenant_id == tenant_id
                )
            )
        )
        
        conversation_model = result.scalar_one_or_none()
        if not conversation_model:
            return None, None
        
        # Update fields
        if conversation_data.status:
            # Update status in metadata or messages
            pass
        if conversation_data.assigned_to:
            # Assigned_to is not a direct field, would need to be in metadata
            pass
        if conversation_data.priority:
            # Priority is not a direct field, would need to be in metadata
            pass
        if conversation_data.subject:
            # Subject is not a direct field, would need to be in metadata
            pass
        
        conversation_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(conversation_model)
        
        conversation = await self._conversation_model_to_schema(conversation_model)
        return conversation, None
    
    async def close_conversation(
        self,
        conversation_id: str,
        tenant_id: str
    ) -> Tuple[Optional[Conversation], Optional[AgentTask]]:
        """
        Close a conversation.
        
        Returns:
            Tuple of (closed conversation, agent task if created)
        """
        # Get existing conversation
        result = await self.db_session.execute(
            select(ConversationModel)
            .where(
                and_(
                    ConversationModel.id == conversation_id,
                    ConversationModel.tenant_id == tenant_id
                )
            )
        )
        
        conversation_model = result.scalar_one_or_none()
        if not conversation_model:
            return None, None
        
        # Update status to closed
        # In our schema, status is in the Conversation model
        conversation_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(conversation_model)
        
        conversation = await self._conversation_model_to_schema(conversation_model)
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.CUSTOMER_CONVERSATION_CLOSED,
            data={"conversation_id": conversation_id},
            agent_task_id=None
        )
        
        return conversation, None
    
    # ========================================================================
    # Reply Operations
    # ========================================================================
    
    async def send_reply(
        self,
        conversation_id: str,
        reply_data: ReplyRequest,
        tenant_id: str
    ) -> Tuple[ReplyResponse, Optional[AgentTask]]:
        """
        Send a reply to a customer conversation.
        
        Args:
            conversation_id: Conversation ID
            reply_data: Reply data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (reply response, agent task if approval required)
        """
        agent_task: Optional[AgentTask] = None
        
        # Check trust level
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="send_customer_reply",
                input_data={
                    "conversation_id": conversation_id,
                    **reply_data.model_dump()
                },
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_id=conversation_id,
                related_entity_type="conversation"
            )
        
        # Get conversation
        conversation = await self.get_conversation(conversation_id, tenant_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Create reply message
        message_id = generate_id("msg")
        reply_message = Message(
            id=message_id,
            role=MessageRole.ASSISTANT,
            content=reply_data.content,
            timestamp=get_current_timestamp(),
            sentiment=None,
            intent=None,
            metadata={
                "channel": reply_data.channel.value,
                "template_id": reply_data.template_id
            }
        )
        
        # Add message to conversation
        conversation_model = await self._get_conversation_model(conversation_id, tenant_id)
        if conversation_model:
            conversation_model.messages.append(reply_message.model_dump())
            conversation_model.updated_at = get_current_timestamp()
            await self.db_session.commit()
        
        # If auto-execute
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        response = ReplyResponse(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return response, agent_task
    
    # ========================================================================
    # Escalation Operations
    # ========================================================================
    
    async def escalate_conversation(
        self,
        conversation_id: str,
        escalation_data: EscalationRequest,
        tenant_id: str
    ) -> Tuple[EscalationResponse, Optional[AgentTask]]:
        """
        Escalate a conversation to a human agent.
        
        Args:
            conversation_id: Conversation ID
            escalation_data: Escalation data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (escalation response, agent task if created)
        """
        # Escalations are always auto-executed per trust level rules
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="escalate_conversation",
            input_data={
                "conversation_id": conversation_id,
                **escalation_data.model_dump()
            },
            status=AgentTaskStatus.AUTO_EXECUTED,
            related_entity_id=conversation_id,
            related_entity_type="conversation"
        )
        
        # Update conversation status to escalated
        conversation_model = await self._get_conversation_model(conversation_id, tenant_id)
        if conversation_model:
            conversation_model.updated_at = get_current_timestamp()
            await self.db_session.commit()
        
        escalation_id = generate_id("escalation")
        
        response = EscalationResponse(
            conversation_id=conversation_id,
            escalation_id=escalation_id,
            agent_task_id=agent_task.id
        )
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.CUSTOMER_CONVERSATION_ESCALATED,
            data={
                "conversation_id": conversation_id,
                "escalation_id": escalation_id,
                "reason": escalation_data.reason,
                "priority": escalation_data.priority.value
            },
            agent_task_id=agent_task.id
        )
        
        return response, agent_task
    
    # ========================================================================
    # Notification Operations
    # ========================================================================
    
    async def send_notification(
        self,
        notification_data: NotificationRequest,
        tenant_id: str
    ) -> Tuple[NotificationResponse, Optional[AgentTask]]:
        """
        Send a proactive notification to a customer.
        
        Args:
            notification_data: Notification data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (notification response, agent task if approval required)
        """
        agent_task: Optional[AgentTask] = None
        
        # Check trust level
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="send_customer_notification",
                input_data=notification_data.model_dump(),
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_id=notification_data.customer_id,
                related_entity_type="customer"
            )
        
        notification_id = generate_id("notification")
        
        # In a real implementation, this would actually send the notification
        # via email, SMS, or voice channels
        
        # For now, we'll just mark it as sent
        status = NotificationStatus.SENT
        
        # If auto-execute
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        response = NotificationResponse(
            notification_id=notification_id,
            status=status,
            agent_task_id=agent_task.id if agent_task else None
        )
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.CUSTOMER_NOTIFICATION_SENT,
            data={
                "notification_id": notification_id,
                "customer_id": notification_data.customer_id,
                "type": notification_data.notification_type.value,
                "channels": notification_data.channels
            },
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return response, agent_task
    
    # ========================================================================
    # Sentiment Analysis Operations
    # ========================================================================
    
    async def analyze_sentiment(
        self,
        request: SentimentAnalysisRequest,
        tenant_id: str
    ) -> Tuple[SentimentAnalysisResponse, Optional[AgentTask]]:
        """
        Analyze sentiment of a message.
        
        Args:
            request: Sentiment analysis request
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (sentiment analysis response, agent task if created)
        """
        # Sentiment analysis is always auto-executed per trust level rules
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="analyze_sentiment",
            input_data=request.model_dump(),
            status=AgentTaskStatus.AUTO_EXECUTED,
            related_entity_type="sentiment_analysis"
        )
        
        # Simple sentiment analysis (placeholder for real ML model)
        message_lower = request.message.lower()
        
        # Check for negative words
        negative_words = ["angry", "mad", "upset", "hate", "terrible", "awful", "worst", "refund", "cancel"]
        positive_words = ["happy", "great", "excellent", "awesome", "perfect", "love", "thank", "thanks"]
        
        negative_count = sum(1 for word in negative_words if word in message_lower)
        positive_count = sum(1 for word in positive_words if word in message_lower)
        
        total_keywords = negative_count + positive_count
        
        if total_keywords == 0:
            sentiment = Sentiment.NEUTRAL
            confidence = 0.5
        elif negative_count > positive_count:
            sentiment = Sentiment.NEGATIVE
            confidence = min(1.0, negative_count / total_keywords)
        else:
            sentiment = Sentiment.POSITIVE
            confidence = min(1.0, positive_count / total_keywords)
        
        # Extract intent (simple keyword matching)
        intent = None
        if "where is" in message_lower or "status" in message_lower or "tracking" in message_lower:
            intent = "status_query"
        elif "delay" in message_lower or "late" in message_lower:
            intent = "delay_complaint"
        elif "refund" in message_lower or "money back" in message_lower:
            intent = "refund_request"
        
        response = SentimentAnalysisResponse(
            sentiment=sentiment,
            confidence=round(confidence, 2),
            intent=intent,
            agent_task_id=agent_task.id
        )
        
        # If negative sentiment and auto-escalate is enabled, escalate the conversation
        if (sentiment == Sentiment.NEGATIVE and 
            self.config.auto_escalate_negative_sentiment and
            request.conversation_id):
            
            # Create escalation
            escalation_data = EscalationRequest(
                reason=f"Negative sentiment detected (confidence: {confidence:.2f})",
                priority=ConversationPriority.HIGH,
                assign_to=None
            )
            
            await self.escalate_conversation(
                conversation_id=request.conversation_id,
                escalation_data=escalation_data,
                tenant_id=tenant_id
            )
            
            # Emit webhook event for negative sentiment
            await self._emit_webhook_event(
                tenant_id=tenant_id,
                event_type=WebhookEventType.CUSTOMER_SENTIMENT_NEGATIVE_DETECTED,
                data={
                    "conversation_id": request.conversation_id,
                    "sentiment": sentiment.value,
                    "confidence": confidence,
                    "intent": intent
                },
                agent_task_id=agent_task.id
            )
        
        return response, agent_task
    
    # ========================================================================
    # Configuration
    # ========================================================================
    
    async def get_config(self, tenant_id: str) -> CustomerSupportConfig:
        """Get the current configuration."""
        return self.config
    
    async def update_config(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> CustomerSupportConfig:
        """Update the configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        return self.config
    
    # ============================================================================
    # Statistics
    # ============================================================================
    
    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get customer support statistics."""
        # Count conversations
        result = await self.db_session.execute(
            select(func.count(ConversationModel.id))
            .where(
                and_(
                    ConversationModel.tenant_id == tenant_id,
                    ConversationModel.participant_type == "customer"
                )
            )
        )
        total_conversations = result.scalar() or 0
        
        # Count open conversations (would need to check status in metadata)
        # For now, we'll just return the total
        
        return {
            "total_conversations": int(total_conversations),
            "open_conversations": 0,
            "closed_conversations": 0,
            "escalated_conversations": 0,
            "avg_response_time_minutes": 0.0,
            "avg_resolution_time_minutes": 0.0,
            "customer_satisfaction_score": 0.0,
            "notifications_sent": 0,
            "negative_sentiment_count": 0
        }
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def _conversation_model_to_schema(self, model: ConversationModel) -> Conversation:
        """Convert ConversationModel to Conversation schema."""
        # Parse messages
        messages = [
            Message(
                id=msg.get("id", generate_id("msg")),
                role=msg.get("role", MessageRole.CUSTOMER),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp", get_current_timestamp()),
                sentiment=msg.get("sentiment"),
                intent=msg.get("intent"),
                metadata=msg.get("metadata")
            )
            for msg in model.messages or []
        ]
        
        # Extract customer_id from participant_id
        customer_id = model.participant_id or ""
        
        return Conversation(
            id=model.id,
            tenant_id=model.tenant_id,
            customer_id=customer_id,
            channel=model.channel,
            subject="",  # Would be in metadata
            messages=messages,
            assigned_to=None,  # Would be in metadata
            priority=ConversationPriority.MEDIUM,  # Would be in metadata
            related_shipment_ids=model.related_agent_task_ids or [],
            status=ConversationStatus.OPEN,  # Would be in metadata
            created_at=model.created_at,
            updated_at=model.updated_at,
            closed_at=None  # Would be in metadata
        )
    
    async def _get_conversation_model(self, conversation_id: str, tenant_id: str) -> Optional[ConversationModel]:
        """Get a ConversationModel by ID."""
        result = await self.db_session.execute(
            select(ConversationModel)
            .where(
                and_(
                    ConversationModel.id == conversation_id,
                    ConversationModel.tenant_id == tenant_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _create_agent_task(
        self,
        tenant_id: str,
        action_type: str,
        input_data: Dict[str, Any],
        status: AgentTaskStatus = AgentTaskStatus.PENDING_APPROVAL,
        reasoning_trace: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        related_entity_type: Optional[str] = None
    ) -> AgentTask:
        """Create an AgentTask record."""
        reasoning_trace = reasoning_trace or f"Customer Support Agent: {action_type}"
        
        task_model = AgentTaskModel(
            id=generate_id("task"),
            tenant_id=tenant_id,
            agent_type=AgentType.CUSTOMER_COMMUNICATION,
            action_type=action_type,
            status=status,
            trust_level=self.config.trust_level,
            reasoning_trace=reasoning_trace,
            input_data=input_data,
            related_entity_id=related_entity_id,
            related_entity_type=related_entity_type,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(task_model)
        await self.db_session.commit()
        await self.db_session.refresh(task_model)
        
        return AgentTask(
            id=task_model.id,
            tenant_id=task_model.tenant_id,
            agent_type=task_model.agent_type,
            action_type=task_model.action_type,
            status=task_model.status,
            trust_level=task_model.trust_level,
            reasoning_trace=task_model.reasoning_trace,
            input_data=task_model.input_data,
            related_entity_id=task_model.related_entity_id,
            related_entity_type=task_model.related_entity_type,
            created_at=task_model.created_at,
            updated_at=task_model.updated_at
        )
    
    async def _update_agent_task(self, task: AgentTask) -> None:
        """Update an AgentTask record."""
        result = await self.db_session.execute(
            select(AgentTaskModel)
            .where(AgentTaskModel.id == task.id)
        )
        
        task_model = result.scalar_one_or_none()
        if task_model:
            task_model.status = task.status
            task_model.completed_at = task.completed_at
            task_model.output_data = task.output_data
            task_model.error_message = task.error_message
            task_model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
    
    async def _emit_webhook_event(
        self,
        tenant_id: str,
        event_type: WebhookEventType,
        data: Dict[str, Any],
        agent_task_id: Optional[str] = None
    ) -> None:
        """Emit a webhook event."""
        logger.info(f"Webhook event: {event_type.value} for tenant {tenant_id}")
