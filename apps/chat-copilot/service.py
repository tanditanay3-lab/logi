"""
Service layer for the Chat Copilot.

This service handles chat conversations and routes them to the appropriate agents
via the Conversation Router in the Orchestrator.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    AgentTask as AgentTaskModel,
    Conversation as ConversationModel,
    Tenant,
)
from packages.shared_types.schemas import (
    AgentType,
    Conversation as ConversationSchema,
    ConversationChannel,
    ConversationMessage,
)
from packages.shared_types.utils import generate_id, get_current_timestamp
from packages.tool_bus.mcp_client import MCPClient

from .config import ChatCopilotConfig
from .schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    ConversationSummary,
    ChatStats,
    MessageRole,
)

logger = logging.getLogger(__name__)


class ChatCopilotService:
    """
    Service for managing chat conversations.
    
    This service:
    - Manages conversation state
    - Routes messages to the Conversation Router
    - Handles conversation history
    - Manages typing indicators
    - Tracks conversation statistics
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config: ChatCopilotConfig,
        tool_client: Optional[MCPClient] = None
    ):
        self.db_session = db_session
        self.config = config
        self.tool_client = tool_client or MCPClient()
        self._active_conversations: Dict[str, Dict[str, Any]] = {}
        self._typing_indicators: Dict[str, bool] = {}
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        logger.info("Chat Copilot Service initialized")
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
        logger.info("Chat Copilot Service closed")
    
    # ========================================================================
    # Conversation Operations
    # ========================================================================
    
    async def send_message(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        """
        Send a message and get a response.
        
        Args:
            request: Chat request
            
        Returns:
            ChatResponse with the agent's response
        """
        # Get or create conversation
        conversation_id = request.conversation_id or generate_id("conv")
        
        # Create conversation if it doesn't exist
        if request.conversation_id is None:
            await self._create_conversation(
                conversation_id=conversation_id,
                tenant_id=request.tenant_id,
                participant_type=request.participant_type,
                participant_id=request.participant_id
            )
        
        # Add user message to conversation
        user_message = ChatMessage(
            id=generate_id("msg"),
            role=MessageRole.USER,
            content=request.message,
            timestamp=get_current_timestamp(),
            metadata=request.metadata
        )
        
        await self._add_message_to_conversation(
            conversation_id=conversation_id,
            message=user_message
        )
        
        # Show typing indicator
        if self.config.typing_indicator_enabled:
            self._typing_indicators[conversation_id] = True
        
        try:
            # Route to Conversation Router
            response = await self._route_to_conversation_router(
                conversation_id=conversation_id,
                message=request.message,
                tenant_id=request.tenant_id,
                participant_type=request.participant_type,
                participant_id=request.participant_id,
                metadata=request.metadata
            )
            
            # Hide typing indicator
            if conversation_id in self._typing_indicators:
                del self._typing_indicators[conversation_id]
            
            # Add assistant message to conversation
            assistant_message = ChatMessage(
                id=response.message_id,
                role=MessageRole.ASSISTANT,
                content=response.response,
                timestamp=response.timestamp,
                metadata={
                    "agent_type": response.agent_type.value if response.agent_type else None,
                    "agent_task_id": response.agent_task_id,
                    "requires_approval": response.requires_approval
                }
            )
            
            await self._add_message_to_conversation(
                conversation_id=conversation_id,
                message=assistant_message
            )
            
            # Update conversation last message time
            await self._update_conversation_last_message(
                conversation_id=conversation_id,
                last_message=response.response,
                last_message_time=get_current_timestamp()
            )
            
            return response
            
        except Exception as e:
            # Hide typing indicator on error
            if conversation_id in self._typing_indicators:
                del self._typing_indicators[conversation_id]
            
            logger.error(f"Error processing message: {e}")
            
            # Return error response
            return ChatResponse(
                conversation_id=conversation_id,
                message_id=generate_id("msg"),
                response=f"Sorry, I encountered an error: {str(e)}",
                agent_type=None,
                agent_task_id=None,
                requires_approval=False,
                confidence=0.0,
                timestamp=get_current_timestamp()
            )
    
    async def _route_to_conversation_router(
        self,
        conversation_id: str,
        message: str,
        tenant_id: str,
        participant_type: str,
        participant_id: Optional[str],
        metadata: Dict[str, Any]
    ) -> ChatResponse:
        """
        Route a message to the Conversation Router.
        
        This calls the Orchestrator's Conversation Router endpoint.
        """
        # In a real implementation, this would call the Orchestrator API
        # For now, we'll simulate the Conversation Router
        
        # Create a conversation request for the orchestrator
        orchestrator_request = {
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "message": message,
            "channel": ConversationChannel.CHAT,
            "participant_type": participant_type,
            "participant_id": participant_id,
            "metadata": metadata
        }
        
        # Simulate calling the Conversation Router
        response = await self._simulate_conversation_router(orchestrator_request)
        
        return ChatResponse(
            conversation_id=conversation_id,
            message_id=response.get("message_id", generate_id("msg")),
            response=response.get("response", "I can help with that."),
            agent_type=response.get("agent_type"),
            agent_task_id=response.get("agent_task_id"),
            requires_approval=response.get("requires_approval", False),
            approval_request_id=response.get("approval_request_id"),
            confidence=response.get("confidence", 0.8),
            timestamp=get_current_timestamp(),
            structured_intent=response.get("structured_intent")
        )
    
    async def _simulate_conversation_router(
        self,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulate the Conversation Router for development.
        
        This will be replaced with actual API calls to the Orchestrator in production.
        """
        message = request.get("message", "").lower()
        conversation_id = request.get("conversation_id", "")
        
        # Extract intent and route to appropriate agent
        if "where is" in message or "tracking" in message or "status" in message or "eta" in message:
            # Shipment Tracking Agent
            tracking_number = "1234567890"  # Extract from message in real implementation
            return {
                "message_id": generate_id("msg"),
                "response": f"Shipment {tracking_number} is currently in transit and will be delivered tomorrow by 2 PM.",
                "agent_type": "shipment-tracking",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "confidence": 0.95,
                "structured_intent": {
                    "intent_type": "status_query",
                    "agent_type": "shipment-tracking",
                    "entities": {"tracking_number": tracking_number},
                    "confidence": 0.95
                }
            }
        
        elif "inventory" in message or "stock" in message or "quantity" in message:
            # Inventory Agent
            return {
                "message_id": generate_id("msg"),
                "response": "Current inventory levels: SKU-001 has 50 units, SKU-002 has 25 units, SKU-003 has 10 units (low stock alert).",
                "agent_type": "inventory",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "confidence": 0.9,
                "structured_intent": {
                    "intent_type": "inventory_check",
                    "agent_type": "inventory",
                    "entities": {},
                    "confidence": 0.9
                }
            }
        
        elif "route" in message or "optimize" in message or "re-optimize" in message:
            # Route Optimization Agent
            return {
                "message_id": generate_id("msg"),
                "response": "I've optimized your routes for tomorrow. Route 1: 5 stops, 120 miles, 4 hours. Route 2: 3 stops, 80 miles, 3 hours.",
                "agent_type": "route-optimization",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "confidence": 0.85,
                "structured_intent": {
                    "intent_type": "route_optimization",
                    "agent_type": "route-optimization",
                    "entities": {},
                    "confidence": 0.85
                }
            }
        
        elif "stuck" in message or "closed" in message or "road closed" in message or "delay" in message:
            # Route Optimization Agent (driver issue)
            return {
                "message_id": generate_id("msg"),
                "response": "I understand there's a road closure. Let me re-optimize your route to avoid it. This may require approval since you have stops in progress.",
                "agent_type": "route-optimization",
                "agent_task_id": generate_id("task"),
                "requires_approval": True,
                "approval_request_id": generate_id("approval"),
                "confidence": 0.9,
                "structured_intent": {
                    "intent_type": "driver_issue",
                    "agent_type": "route-optimization",
                    "entities": {"issue": "road_closure"},
                    "confidence": 0.9
                }
            }
        
        elif "complaint" in message or "refund" in message or "compensation" in message:
            # Customer Communication Agent
            return {
                "message_id": generate_id("msg"),
                "response": "I understand you have a complaint. Let me transfer you to a human agent who can better assist you.",
                "agent_type": "customer-communication",
                "agent_task_id": generate_id("task"),
                "requires_approval": True,
                "confidence": 0.95,
                "structured_intent": {
                    "intent_type": "customer_complaint",
                    "agent_type": "customer-communication",
                    "entities": {},
                    "confidence": 0.95
                }
            }
        
        else:
            # Default to Customer Communication Agent
            return {
                "message_id": generate_id("msg"),
                "response": "I can help with that. Could you please provide more details about what you need?",
                "agent_type": "customer-communication",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "confidence": 0.7,
                "structured_intent": {
                    "intent_type": "general_question",
                    "agent_type": "customer-communication",
                    "entities": {},
                    "confidence": 0.7
                }
            }
    
    # ========================================================================
    # Conversation Management
    # ========================================================================
    
    async def list_conversations(
        self,
        tenant_id: str,
        participant_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> ConversationListResponse:
        """List conversations for a tenant."""
        query = select(ConversationModel).where(ConversationModel.tenant_id == tenant_id)
        
        if participant_id:
            query = query.where(ConversationModel.participant_id == participant_id)
        
        # Count total
        count_result = await self.db_session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Get results
        query = query.order_by(desc(ConversationModel.updated_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        conversation_models = result.scalars().all()
        
        conversations = []
        for model in conversation_models:
            summary = ConversationSummary(
                id=model.id,
                tenant_id=model.tenant_id,
                participant_type=model.participant_type,
                participant_id=model.participant_id,
                message_count=len(model.messages or []),
                last_message=model.messages[-1].get("content", "") if model.messages else None,
                last_message_time=model.updated_at,
                agent_types=[],  # Would extract from messages
                status="open"
            )
            conversations.append(summary)
        
        return ConversationListResponse(
            conversations=conversations,
            total=total,
            limit=limit,
            offset=offset
        )
    
    async def get_conversation(
        self,
        conversation_id: str,
        tenant_id: str
    ) -> Optional[ConversationSchema]:
        """Get a conversation by ID."""
        result = await self.db_session.execute(
            select(ConversationModel).where(
                and_(
                    ConversationModel.id == conversation_id,
                    ConversationModel.tenant_id == tenant_id
                )
            )
        )
        
        model = result.scalar_one_or_none()
        if not model:
            return None
        
        return ConversationSchema(
            id=model.id,
            tenant_id=model.tenant_id,
            channel=model.channel,
            participant_type=model.participant_type,
            participant_id=model.participant_id,
            messages=[
                ConversationMessage(
                    id=msg.get("id", ""),
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp", get_current_timestamp()),
                    metadata=msg.get("metadata", {})
                )
                for msg in (model.messages or [])
            ],
            related_agent_task_ids=model.related_agent_task_ids or [],
            voice_call_id=model.voice_call_id,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
    
    async def delete_conversation(
        self,
        conversation_id: str,
        tenant_id: str
    ) -> bool:
        """Delete a conversation."""
        result = await self.db_session.execute(
            select(ConversationModel).where(
                and_(
                    ConversationModel.id == conversation_id,
                    ConversationModel.tenant_id == tenant_id
                )
            )
        )
        
        model = result.scalar_one_or_none()
        if not model:
            return False
        
        await self.db_session.delete(model)
        await self.db_session.commit()
        
        return True
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    async def _create_conversation(
        self,
        conversation_id: str,
        tenant_id: str,
        participant_type: str,
        participant_id: Optional[str] = None
    ):
        """Create a new conversation."""
        conversation_model = ConversationModel(
            id=conversation_id,
            tenant_id=tenant_id,
            channel=ConversationChannel.CHAT,
            participant_type=participant_type,
            participant_id=participant_id,
            messages=[],
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(conversation_model)
        await self.db_session.commit()
        
        logger.info(f"Created conversation {conversation_id} for tenant {tenant_id}")
    
    async def _add_message_to_conversation(
        self,
        conversation_id: str,
        message: ChatMessage
    ):
        """Add a message to a conversation."""
        result = await self.db_session.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        
        model = result.scalar_one_or_none()
        if model:
            if not model.messages:
                model.messages = []
            
            model.messages.append({
                "id": message.id,
                "role": message.role.value,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata or {}
            })
            
            model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
            
            logger.debug(f"Added message {message.id} to conversation {conversation_id}")
    
    async def _update_conversation_last_message(
        self,
        conversation_id: str,
        last_message: str,
        last_message_time: datetime
    ):
        """Update the last message in a conversation."""
        result = await self.db_session.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        
        model = result.scalar_one_or_none()
        if model:
            model.updated_at = last_message_time
            await self.db_session.commit()
    
    # ============================================================================
    # Statistics
    # ============================================================================
    
    async def get_stats(self, tenant_id: str) -> ChatStats:
        """Get chat statistics."""
        # Count conversations
        conv_result = await self.db_session.execute(
            select(func.count(ConversationModel.id))
            .where(ConversationModel.tenant_id == tenant_id)
        )
        total_conversations = conv_result.scalar()
        
        # Count active conversations (updated in last 24 hours)
        active_result = await self.db_session.execute(
            select(func.count(ConversationModel.id))
            .where(
                and_(
                    ConversationModel.tenant_id == tenant_id,
                    ConversationModel.updated_at >= get_current_timestamp() - timedelta(hours=24)
                )
            )
        )
        active_conversations = active_result.scalar()
        
        # Count messages today
        from datetime import datetime, timezone
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        messages_result = await self.db_session.execute(
            select(func.count())
            .select_from(ConversationModel)
            .where(
                and_(
                    ConversationModel.tenant_id == tenant_id,
                    ConversationModel.updated_at >= today_start
                )
            )
        )
        messages_today = messages_result.scalar() or 0
        
        # Calculate average response time (simplified)
        avg_response_time = 2.5  # Seconds (would calculate from actual data)
        
        # Get agent usage (simplified)
        agent_usage = {
            "shipment-tracking": 42,
            "inventory": 35,
            "route-optimization": 23,
            "customer-communication": 15,
            "voice": 5
        }
        
        return ChatStats(
            total_conversations=total_conversations,
            active_conversations=active_conversations,
            messages_today=messages_today,
            avg_response_time_seconds=avg_response_time,
            agent_usage=agent_usage
        )
    
    # ============================================================================
    # Configuration Management
    # ============================================================================
    
    async def get_config(self, tenant_id: str) -> ChatCopilotConfig:
        """Get the current configuration."""
        return self.config
    
    async def update_config(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> ChatCopilotConfig:
        """Update the configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        return self.config
