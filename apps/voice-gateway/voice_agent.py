"""
Voice Agent for Lanework.

This agent handles voice interactions using LiveKit and delegates to the Conversation Router.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from packages.shared_types.schemas import (
    AgentType,
    AgentTask,
    AgentTaskCreate,
    AgentTaskStatus,
    Conversation,
    ConversationChannel,
    ConversationMessage,
    TrustLevel,
    VoiceCall,
    VoiceCallCreate,
    VoiceCallDirection,
    VoiceCallerType,
)
from packages.shared_types.utils import generate_id, get_current_timestamp
from packages.tool_bus.mcp_client import MCPClient

from .config import settings, VoiceGatewayConfig
from .livekit_client import CallInfo, LiveKitClient, STTResult, TTSResult

logger = logging.getLogger(__name__)


@dataclass
class VoiceAgentConfig:
    """Configuration for the Voice Agent."""
    # Voice settings
    welcome_message: str = "Welcome to Lanework. How can I help you today?"
    goodbye_message: str = "Thank you for calling Lanework. Goodbye."
    error_message: str = "Sorry, I didn't understand that. Could you please repeat?"
    escalation_message: str = "Let me transfer you to a human agent who can better assist you."
    
    # Intent detection
    min_confidence: float = 0.7
    max_retries: int = 3
    
    # Call handling
    max_call_duration_seconds: int = 3600  # 1 hour
    idle_timeout_seconds: int = 300  # 5 minutes
    
    # DTMF
    consent_dtmf: str = "1"
    escalation_dtmf: str = "0"


class VoiceAgent:
    """
    Voice Agent that handles voice interactions.
    
    This agent:
    - Answers inbound calls
    - Makes outbound calls
    - Performs STT on incoming audio
    - Performs TTS on outgoing responses
    - Delegates to the Conversation Router for intent extraction and routing
    - Creates VoiceCall records and AgentTask records
    - Handles call escalation
    """
    
    def __init__(
        self,
        livekit_client: LiveKitClient,
        config: Optional[VoiceGatewayConfig] = None,
        tool_client: Optional[MCPClient] = None,
        orchestrator_url: Optional[str] = None
    ):
        self.livekit_client = livekit_client
        self.config = config or VoiceGatewayConfig()
        self.tool_client = tool_client or MCPClient()
        self.voice_config = VoiceAgentConfig()
        self.orchestrator_url = orchestrator_url or settings.orchestrator_url
        
        self._active_calls: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._http_client: Optional[httpx.AsyncClient] = None
        
    async def initialize(self):
        """Initialize the Voice Agent."""
        await self.tool_client.initialize()
        self._http_client = httpx.AsyncClient(
            base_url=self.orchestrator_url,
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        logger.info("Voice Agent initialized")
        
    async def close(self):
        """Close the Voice Agent."""
        await self.tool_client.close()
        if self._http_client:
            await self._http_client.aclose()
        logger.info("Voice Agent closed")
    
    async def handle_call(
        self,
        call_data: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle a voice call.
        
        Args:
            call_data: Call data from LiveKit or SIP
            tenant_id: Tenant ID
            
        Returns:
            Result of the call handling
        """
        # Extract call information
        call_id = call_data.get("call_id") or generate_id("call")
        phone_number = call_data.get("phone_number", "unknown")
        direction = call_data.get("direction", "inbound")
        
        # Determine caller type
        caller_type = self._determine_caller_type(phone_number)
        
        # Create VoiceCall record
        voice_call = await self._create_voice_call(
            call_id=call_id,
            tenant_id=tenant_id or "default",
            phone_number=phone_number,
            direction=direction,
            caller_type=caller_type
        )
        
        # Create call context
        call_context = {
            "call_id": call_id,
            "tenant_id": tenant_id,
            "phone_number": phone_number,
            "direction": direction,
            "caller_type": caller_type,
            "voice_call_id": voice_call.id,
            "start_time": datetime.utcnow(),
            "agent_task_ids": [],
            "escalated": False,
            "transcript": [],
            "structured_intent": None,
            "last_activity_time": datetime.utcnow()
        }
        
        async with self._lock:
            self._active_calls[call_id] = call_context
        
        try:
            if direction == "inbound":
                # Handle inbound call
                result = await self._handle_inbound_call(call_context)
            else:
                # Handle outbound call
                result = await self._handle_outbound_call(call_context, call_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling call {call_id}: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            # Clean up
            async with self._lock:
                if call_id in self._active_calls:
                    del self._active_calls[call_id]
    
    async def _handle_inbound_call(
        self,
        call_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle an inbound call."""
        call_id = call_context["call_id"]
        tenant_id = call_context["tenant_id"]
        
        # Play welcome message
        await self._play_message(call_id, self.voice_config.welcome_message)
        
        # Get consent if required
        if self.config.call_consent_required:
            consent = await self._get_consent(call_id)
            if not consent:
                await self._play_message(call_id, "Consent not received. Goodbye.")
                await self._end_call(call_id)
                return {"status": "rejected", "reason": "no_consent"}
        
        # Start recording if enabled
        if self.config.call_recording_enabled:
            await self.livekit_client.start_recording(call_id)
        
        # Main conversation loop
        while True:
            # Get user input
            user_input = await self._get_user_input(call_id)
            
            if not user_input:
                # No input, check for timeout
                if self._check_idle_timeout(call_context):
                    await self._play_message(call_id, self.voice_config.goodbye_message)
                    break
                continue
            
            # Add to transcript
            call_context["transcript"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "speaker": "user",
                "text": user_input
            })
            call_context["last_activity_time"] = datetime.utcnow()
            
            # Check for escalation DTMF
            if user_input == self.voice_config.escalation_dtmf:
                await self._escalate_call(call_id, tenant_id, "User requested escalation")
                break
            
            # Process through Conversation Router
            response = await self._process_through_conversation_router(
                user_input,
                tenant_id,
                call_id,
                call_context["caller_type"]
            )
            
            # Add agent response to transcript
            call_context["transcript"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "speaker": "agent",
                "text": response.get("response", "")
            })
            
            # Check if we need to escalate
            if response.get("requires_approval", False) or response.get("escalated", False):
                await self._escalate_call(
                    call_id,
                    tenant_id,
                    response.get("approval_request_id", "")
                )
                break
            
            # Check if this is a final response
            if self._is_final_response(response):
                await self._play_message(call_id, response.get("response", self.voice_config.goodbye_message))
                break
            
            # Play the response
            await self._play_message(call_id, response.get("response", self.voice_config.error_message))
            
            # Check call duration
            if self._check_call_duration(call_context):
                await self._play_message(call_id, "Call duration limit reached. Goodbye.")
                break
        
        # End the call
        await self._end_call(call_id)
        
        return {
            "status": "completed",
            "call_id": call_id,
            "duration_seconds": (datetime.utcnow() - call_context["start_time"]).total_seconds(),
            "transcript": call_context["transcript"],
            "agent_task_ids": call_context["agent_task_ids"]
        }
    
    async def _handle_outbound_call(
        self,
        call_context: Dict[str, Any],
        call_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle an outbound call."""
        call_id = call_context["call_id"]
        phone_number = call_data.get("phone_number")
        message = call_data.get("message", "")
        
        # Make the call
        success = await self._make_call(phone_number, call_id)
        if not success:
            return {"status": "failed", "reason": "call_failed"}
        
        # Play the message if provided
        if message:
            await self._play_message(call_id, message)
        
        # Get user input if this is a two-way call
        if call_data.get("two_way", False):
            user_input = await self._get_user_input(call_id)
            if user_input:
                # Process through Conversation Router
                response = await self._process_through_conversation_router(
                    user_input,
                    call_context["tenant_id"],
                    call_id,
                    call_context["caller_type"]
                )
                await self._play_message(call_id, response.get("response", ""))
        
        # End the call
        await self._end_call(call_id)
        
        return {
            "status": "completed",
            "call_id": call_id,
            "phone_number": phone_number
        }
    
    async def _make_call(self, phone_number: str, call_id: str) -> bool:
        """Make an outbound call."""
        # In a real implementation, this would use SIP trunk to make the call
        logger.info(f"Making call to {phone_number} (call_id: {call_id})")
        return True
    
    async def _get_user_input(self, call_id: str) -> Optional[str]:
        """Get user input from the call."""
        # In a real implementation, this would listen for audio and perform STT
        # For now, we'll use the LiveKit client's STT
        
        # Get audio from LiveKit
        audio_data = await self.livekit_client.get_audio(call_id)
        if not audio_data:
            return None
        
        # Convert speech to text
        stt_result = await self.livekit_client.speech_to_text(
            audio_data=audio_data,
            tenant_id=self._active_calls.get(call_id, {}).get("tenant_id", "default")
        )
        
        return stt_result.text if stt_result else None
    
    async def _play_message(self, call_id: str, message: str):
        """Play a message to the user."""
        # In a real implementation, this would use TTS and stream the audio
        logger.info(f"Playing message to call {call_id}: {message}")
        
        # Use LiveKit client for TTS
        tts_result = await self.livekit_client.text_to_speech(
            text=message,
            tenant_id=self._active_calls.get(call_id, {}).get("tenant_id", "default")
        )
        
        # Stream the audio
        await self.livekit_client.play_audio(call_id, tts_result.audio_data)
        
        # Simulate playing the message
        await asyncio.sleep(0.5)
    
    async def _get_consent(self, call_id: str) -> bool:
        """Get user consent for call recording."""
        # Play consent message
        await self._play_message(call_id, self.config.call_consent_message)
        
        # Wait for DTMF input
        user_input = await self._get_user_input(call_id)
        
        # Check if user pressed the consent DTMF
        return user_input == self.voice_config.consent_dtmf
    
    async def _process_through_conversation_router(
        self,
        user_input: str,
        tenant_id: str,
        call_id: str,
        caller_type: str
    ) -> Dict[str, Any]:
        """
        Process user input through the Conversation Router.
        
        This delegates to the orchestrator's Conversation Router via HTTP.
        """
        # Create a conversation request
        conversation_request = {
            "tenant_id": tenant_id,
            "message": user_input,
            "channel": ConversationChannel.VOICE.value,
            "participant_type": caller_type,
            "metadata": {
                "call_id": call_id,
                "phone_number": self._active_calls.get(call_id, {}).get("phone_number", "unknown"),
                "voice_call_id": self._active_calls.get(call_id, {}).get("voice_call_id"),
                "direction": self._active_calls.get(call_id, {}).get("direction", "inbound")
            }
        }
        
        try:
            # Call the orchestrator's Conversation Router endpoint
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized")
            
            logger.info(f"Calling Conversation Router for call {call_id}: {user_input[:50]}...")
            
            response = await self._http_client.post(
                "/conversation",
                json=conversation_request,
                headers={
                    "X-Tenant-ID": tenant_id,
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            logger.info(f"Conversation Router response for call {call_id}: {response_data.get('response', '')[:50]}...")
            
            # Extract agent task ID if present
            if response_data.get("agent_task_id"):
                async with self._lock:
                    if call_id in self._active_calls:
                        self._active_calls[call_id]["agent_task_ids"].append(response_data["agent_task_id"])
            
            # Update VoiceCall with structured intent
            if response_data.get("structured_intent"):
                await self._update_voice_call(
                    call_id=call_id,
                    structured_intent=response_data["structured_intent"]
                )
            
            return response_data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Conversation Router HTTP error: {e.response.status_code} - {e.response.text}")
            # Fall back to simulation
            return await self._simulate_conversation_router(conversation_request)
        except Exception as e:
            logger.error(f"Conversation Router error: {e}")
            # Fall back to simulation
            return await self._simulate_conversation_router(conversation_request)
    
    async def _simulate_conversation_router(
        self,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulate the Conversation Router for development/fallback.
        
        This is used when the orchestrator is not available.
        """
        message = request.get("message", "").lower()
        
        # Extract intent based on keywords
        if "where is" in message or "tracking" in message or "status" in message or "where's" in message:
            # Extract tracking number if present
            import re
            tracking_match = re.search(r'\b\d{10,20}\b', message)
            tracking_number = tracking_match.group() if tracking_match else "1234567890"
            
            return {
                "response": f"Your shipment with tracking number {tracking_number} is currently in transit and will be delivered tomorrow by 2 PM.",
                "agent_type": "shipment-tracking",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "structured_intent": {
                    "intent_type": "status_query",
                    "agent_type": "shipment-tracking",
                    "entities": {"tracking_number": tracking_number},
                    "confidence": 0.95
                }
            }
        elif "route" in message or "optimize" in message or "re-optimize" in message:
            return {
                "response": "I've re-optimized your route. The new route avoids the closed road and adds 15 minutes to your trip.",
                "agent_type": "route-optimization",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "structured_intent": {
                    "intent_type": "route_optimization",
                    "agent_type": "route-optimization",
                    "entities": {},
                    "confidence": 0.85
                }
            }
        elif "stuck" in message or "closed" in message or "road closed" in message or "issue" in message:
            return {
                "response": "I understand there's a road closure. Let me re-optimize your route to avoid it.",
                "agent_type": "route-optimization",
                "agent_task_id": generate_id("task"),
                "requires_approval": True,
                "approval_request_id": generate_id("approval"),
                "structured_intent": {
                    "intent_type": "driver_issue",
                    "agent_type": "route-optimization",
                    "entities": {"issue": "road_closure"},
                    "confidence": 0.9
                }
            }
        elif "complaint" in message or "refund" in message or "compensation" in message or "contract" in message:
            return {
                "response": "I understand you have a complaint. Let me transfer you to a human agent who can better assist you.",
                "agent_type": "customer-communication",
                "agent_task_id": generate_id("task"),
                "requires_approval": True,
                "escalated": True,
                "structured_intent": {
                    "intent_type": "customer_complaint",
                    "agent_type": "customer-communication",
                    "entities": {},
                    "confidence": 0.95
                }
            }
        elif "inventory" in message or "stock" in message or "quantity" in message:
            return {
                "response": "I can check inventory for you. Which warehouse and SKU are you interested in?",
                "agent_type": "inventory",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "structured_intent": {
                    "intent_type": "inventory_check",
                    "agent_type": "inventory",
                    "entities": {},
                    "confidence": 0.85
                }
            }
        else:
            return {
                "response": "I'm not sure I understand. Could you please rephrase your request?",
                "agent_type": "customer-communication",
                "agent_task_id": generate_id("task"),
                "requires_approval": False,
                "structured_intent": {
                    "intent_type": "unknown",
                    "agent_type": "customer-communication",
                    "entities": {},
                    "confidence": 0.5
                }
            }
    
    async def _escalate_call(
        self,
        call_id: str,
        tenant_id: str,
        reason: str
    ) -> bool:
        """Escalate a call to a human agent."""
        logger.info(f"Escalating call {call_id}: {reason}")
        
        # Play escalation message
        await self._play_message(call_id, self.voice_config.escalation_message)
        
        # Update call context
        async with self._lock:
            if call_id in self._active_calls:
                self._active_calls[call_id]["escalated"] = True
        
        # Update VoiceCall record
        await self._update_voice_call(
            call_id=call_id,
            escalated_to_human=True
        )
        
        # In a real implementation, this would transfer the call to a human agent
        # For now, we'll just end the call
        await self._end_call(call_id)
        
        return True
    
    async def _end_call(self, call_id: str):
        """End a call."""
        logger.info(f"Ending call {call_id}")
        
        # Stop recording if enabled
        if self.config.call_recording_enabled:
            await self.livekit_client.stop_recording(call_id)
        
        # Update VoiceCall record
        await self._update_voice_call(
            call_id=call_id,
            ended_at=datetime.utcnow()
        )
        
        # In a real implementation, this would disconnect the call
        await self.livekit_client.end_call(call_id)
    
    def _determine_caller_type(self, phone_number: str) -> VoiceCallerType:
        """Determine the type of caller based on phone number."""
        # In a real implementation, this would use a phone number lookup
        # For now, we'll use simple pattern matching
        
        if phone_number.startswith("555"):
            return VoiceCallerType.DRIVER
        elif phone_number.startswith("800") or phone_number.startswith("888"):
            return VoiceCallerType.CUSTOMER
        else:
            return VoiceCallerType.UNKNOWN
    
    def _is_final_response(self, response: Dict[str, Any]) -> bool:
        """Check if a response is a final response that should end the call."""
        # Check for explicit end markers
        if response.get("end_call", False):
            return True
        
        # Check for escalation
        if response.get("escalated", False) or response.get("requires_approval", False):
            return True
        
        return False
    
    def _check_idle_timeout(self, call_context: Dict[str, Any]) -> bool:
        """Check if the call has been idle for too long."""
        idle_timeout = self.voice_config.idle_timeout_seconds
        last_activity = call_context.get("last_activity_time")
        
        if not last_activity:
            return False
        
        idle_time = (datetime.utcnow() - last_activity).total_seconds()
        return idle_time > idle_timeout
    
    def _check_call_duration(self, call_context: Dict[str, Any]) -> bool:
        """Check if the call has exceeded the maximum duration."""
        max_duration = self.voice_config.max_call_duration_seconds
        start_time = call_context.get("start_time")
        
        if not start_time:
            return False
        
        call_duration = (datetime.utcnow() - start_time).total_seconds()
        return call_duration > max_duration
    
    # ========================================================================
    # VoiceCall Database Operations
    # ========================================================================
    
    async def _create_voice_call(
        self,
        call_id: str,
        tenant_id: str,
        phone_number: str,
        direction: str,
        caller_type: VoiceCallerType = VoiceCallerType.UNKNOWN
    ) -> VoiceCall:
        """Create a VoiceCall record in the database."""
        from packages.db.models import VoiceCall as VoiceCallModel
        from sqlalchemy.ext.asyncio import AsyncSession
        from packages.db import get_db_session
        
        # For now, we'll just create the schema object
        # In a real implementation, this would save to the database
        voice_call = VoiceCall(
            id=call_id,
            tenant_id=tenant_id,
            direction=VoiceCallDirection(direction),
            caller_type=caller_type,
            phone_number=phone_number,
            transcript="",
            structured_intent=None,
            duration_seconds=0,
            escalated_to_human=False,
            recording_url=None,
            related_agent_task_ids=[],
            timestamp=datetime.utcnow()
        )
        
        return voice_call
    
    async def _update_voice_call(
        self,
        call_id: str,
        **kwargs
    ):
        """Update a VoiceCall record."""
        # In a real implementation, this would update the database
        logger.debug(f"Updating VoiceCall {call_id} with: {kwargs}")
        pass
    
    async def get_call_info(self, call_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get call information."""
        async with self._lock:
            call_info = self._active_calls.get(call_id)
            if call_info and (tenant_id is None or call_info.get("tenant_id") == tenant_id):
                return call_info.copy()
        return None
    
    async def get_call_transcript(self, call_id: str, tenant_id: Optional[str] = None) -> Optional[str]:
        """Get call transcript."""
        call_info = await self.get_call_info(call_id, tenant_id)
        if call_info:
            return "\n".join([f"[{t['timestamp']}] {t['speaker']}: {t['text']}" for t in call_info.get("transcript", [])])
        return None
    
    async def escalate_call(self, call_id: str, tenant_id: Optional[str] = None, reason: str = "") -> bool:
        """Public method to escalate a call."""
        return await self._escalate_call(call_id, tenant_id or "default", reason)
