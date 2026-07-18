"""
LiveKit client for the Voice Gateway.

This client handles the integration with LiveKit for:
- WebRTC connections
- SIP trunk integration
- STT (Speech-to-Text)
- TTS (Text-to-Speech)
- Call management
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel

from .config import settings, VoiceGatewayConfig

logger = logging.getLogger(__name__)


@dataclass
class CallInfo:
    """Information about an active call."""
    call_id: str
    tenant_id: str
    phone_number: str
    direction: str  # "inbound" or "outbound"
    status: str  # "dialing", "connected", "disconnected", "failed"
    start_time: datetime
    end_time: Optional[datetime] = None
    participant_id: Optional[str] = None
    room_name: Optional[str] = None
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    structured_intent: Optional[Dict[str, Any]] = None
    agent_type: Optional[str] = None
    agent_task_ids: List[str] = field(default_factory=list)
    escalated_to_human: bool = False


@dataclass
class STTResult:
    """Result from Speech-to-Text."""
    text: str
    confidence: float
    language: str
    duration_seconds: float
    timestamp: datetime


@dataclass
class TTSResult:
    """Result from Text-to-Speech."""
    audio_data: bytes
    format: str  # "wav", "mp3", "ogg"
    duration_seconds: float
    timestamp: datetime


class LiveKitClient:
    """
    Client for interacting with LiveKit.
    
    This client handles:
    - Connecting to LiveKit server
    - Managing rooms and participants
    - SIP trunk integration
    - STT and TTS processing
    - Call recording
    """
    
    def __init__(self, config: Optional[VoiceGatewayConfig] = None):
        self.config = config or get_default_config()
        self._client: Optional[httpx.AsyncClient] = None
        self._active_calls: Dict[str, CallInfo] = {}
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the LiveKit client."""
        self._client = httpx.AsyncClient(
            base_url=f"http://{self.config.livekit_host}:{self.config.livekit_port}",
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        
        # Initialize the room
        await self._initialize_room()
        
        logger.info("LiveKit client initialized")
        
    async def close(self):
        """Close the LiveKit client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        
        logger.info("LiveKit client closed")
        
    async def _initialize_room(self):
        """Initialize the LiveKit room for voice calls."""
        # In a real implementation, this would create the room if it doesn't exist
        # For now, we'll just log that we're initializing
        logger.info(f"Initializing LiveKit room: {self.config.livekit_room_name}")
        
    async def create_call(
        self,
        phone_number: str,
        tenant_id: str,
        direction: str = "outbound",
        caller_id: Optional[str] = None
    ) -> CallInfo:
        """
        Create a new voice call.
        
        Args:
            phone_number: Phone number to call (for outbound) or from (for inbound)
            tenant_id: Tenant ID
            direction: Call direction ("inbound" or "outbound")
            caller_id: Optional caller ID to display
            
        Returns:
            CallInfo with the call details
        """
        call_id = f"call_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        call_info = CallInfo(
            call_id=call_id,
            tenant_id=tenant_id,
            phone_number=phone_number,
            direction=direction,
            status="dialing" if direction == "outbound" else "connected",
            start_time=datetime.utcnow(),
            room_name=self.config.livekit_room_name
        )
        
        async with self._lock:
            self._active_calls[call_id] = call_info
        
        # In a real implementation, this would connect to LiveKit and initiate the call
        logger.info(f"Created call {call_id} for {phone_number} ({direction})")
        
        return call_info
    
    async def end_call(self, call_id: str) -> bool:
        """
        End an active call.
        
        Args:
            call_id: ID of the call to end
            
        Returns:
            True if the call was ended successfully
        """
        async with self._lock:
            call_info = self._active_calls.get(call_id)
            if not call_info:
                return False
            
            call_info.status = "disconnected"
            call_info.end_time = datetime.utcnow()
        
        # In a real implementation, this would disconnect from LiveKit
        logger.info(f"Ended call {call_id}")
        
        return True
    
    async def get_call_info(self, call_id: str) -> Optional[CallInfo]:
        """
        Get information about an active call.
        
        Args:
            call_id: ID of the call
            
        Returns:
            CallInfo if the call exists, None otherwise
        """
        async with self._lock:
            return self._active_calls.get(call_id)
    
    async def list_active_calls(self, tenant_id: Optional[str] = None) -> List[CallInfo]:
        """
        List all active calls.
        
        Args:
            tenant_id: Optional tenant ID to filter by
            
        Returns:
            List of active CallInfo objects
        """
        async with self._lock:
            calls = list(self._active_calls.values())
        
        if tenant_id:
            calls = [c for c in calls if c.tenant_id == tenant_id]
        
        return calls
    
    async def speech_to_text(
        self,
        audio_data: bytes,
        tenant_id: str,
        language: Optional[str] = None
    ) -> STTResult:
        """
        Convert speech audio to text.
        
        Args:
            audio_data: Audio data in bytes
            tenant_id: Tenant ID
            language: Optional language code
            
        Returns:
            STTResult with the transcribed text
        """
        # In a real implementation, this would call the STT engine
        # For now, we'll simulate a simple transcription
        
        # Simulate transcription based on audio size
        duration_seconds = len(audio_data) / (16000 * 2)  # Assuming 16kHz, 16-bit audio
        
        # Simulate some text
        text = "This is a simulated transcription of the audio."
        
        logger.info(f"Transcribed {duration_seconds:.2f} seconds of audio")
        
        return STTResult(
            text=text,
            confidence=0.95,
            language=language or self.config.stt_language,
            duration_seconds=duration_seconds,
            timestamp=datetime.utcnow()
        )
    
    async def text_to_speech(
        self,
        text: str,
        tenant_id: str,
        voice: Optional[str] = None
    ) -> TTSResult:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to convert to speech
            tenant_id: Tenant ID
            voice: Optional voice to use
            
        Returns:
            TTSResult with audio data
        """
        # In a real implementation, this would call the TTS engine
        # For now, we'll return a simple WAV file with silence
        
        import struct
        
        # Create a simple WAV file with silence
        sample_rate = 16000
        duration = len(text) * 0.1  # Roughly 100ms per character
        num_samples = int(sample_rate * duration)
        
        # WAV header
        wav_header = b'RIFF' + struct.pack('<I', 36 + num_samples * 2)
        wav_header += b'WAVEfmt ' + struct.pack('<I', 16)
        wav_header += struct.pack('<H', 1)  # PCM format
        wav_header += struct.pack('<H', 1)  # Mono
        wav_header += struct.pack('<I', sample_rate)
        wav_header += struct.pack('<I', sample_rate * 2)  # Byte rate
        wav_header += struct.pack('<H', 2)  # Block align
        wav_header += struct.pack('<H', 16)  # Bits per sample
        wav_header += b'data' + struct.pack('<I', num_samples * 2)
        
        # Silence data
        audio_data = wav_header + b'\x00\x00' * num_samples
        
        logger.info(f"Generated {duration:.2f} seconds of TTS audio")
        
        return TTSResult(
            audio_data=audio_data,
            format="wav",
            duration_seconds=duration,
            timestamp=datetime.utcnow()
        )
    
    async def start_recording(self, call_id: str) -> bool:
        """
        Start recording a call.
        
        Args:
            call_id: ID of the call to record
            
        Returns:
            True if recording started successfully
        """
        async with self._lock:
            call_info = self._active_calls.get(call_id)
            if not call_info:
                return False
        
        # In a real implementation, this would start recording in LiveKit
        logger.info(f"Started recording for call {call_id}")
        
        return True
    
    async def stop_recording(self, call_id: str) -> Optional[str]:
        """
        Stop recording a call and get the recording URL.
        
        Args:
            call_id: ID of the call
            
        Returns:
            URL of the recording if successful, None otherwise
        """
        async with self._lock:
            call_info = self._active_calls.get(call_id)
            if not call_info:
                return None
        
        # In a real implementation, this would stop recording and upload to storage
        recording_url = f"https://{self.config.call_recording_bucket}.s3.amazonaws.com/{call_id}.wav"
        
        async with self._lock:
            call_info.recording_url = recording_url
        
        logger.info(f"Stopped recording for call {call_id}, URL: {recording_url}")
        
        return recording_url
    
    async def connect_to_room(
        self,
        room_name: str,
        participant_name: str,
        participant_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Connect to a LiveKit room.
        
        Args:
            room_name: Name of the room to connect to
            participant_name: Name of the participant
            participant_metadata: Optional metadata for the participant
            
        Returns:
            Participant ID
        """
        # In a real implementation, this would connect to the LiveKit room
        participant_id = f"participant_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        logger.info(f"Connected to room {room_name} as {participant_name} ({participant_id})")
        
        return participant_id
    
    async def disconnect_from_room(self, participant_id: str) -> bool:
        """
        Disconnect from a LiveKit room.
        
        Args:
            participant_id: ID of the participant to disconnect
            
        Returns:
            True if disconnected successfully
        """
        logger.info(f"Disconnected participant {participant_id}")
        return True
    
    async def send_audio(
        self,
        participant_id: str,
        audio_data: bytes
    ) -> bool:
        """
        Send audio data to a participant.
        
        Args:
            participant_id: ID of the participant to send audio to
            audio_data: Audio data in bytes
            
        Returns:
            True if audio was sent successfully
        """
        # In a real implementation, this would send audio through LiveKit
        logger.debug(f"Sent {len(audio_data)} bytes of audio to {participant_id}")
        return True
    
    async def receive_audio(
        self,
        participant_id: str,
        callback: Callable[[bytes], None]
    ) -> None:
        """
        Start receiving audio from a participant.
        
        Args:
            participant_id: ID of the participant to receive audio from
            callback: Callback function to receive audio data
        """
        # In a real implementation, this would set up a listener for audio
        logger.info(f"Started receiving audio from {participant_id}")
        
        # For simulation, we'll just log that we're receiving
        # In a real implementation, this would be an async stream
    
    async def get_audio(self, call_id: str) -> Optional[bytes]:
        """
        Get audio data from a call.
        
        Args:
            call_id: ID of the call
            
        Returns:
            Audio data in bytes, or None if no audio available
        """
        # In a real implementation, this would get audio from the LiveKit call
        # For simulation, we'll return some dummy audio data
        
        # Simulate getting audio from the call
        # This would be replaced with actual audio capture in production
        import struct
        sample_rate = 16000
        duration = 2.0  # 2 seconds of audio
        num_samples = int(sample_rate * duration)
        
        # WAV header
        wav_header = b'RIFF' + struct.pack('<I', 36 + num_samples * 2)
        wav_header += b'WAVEfmt ' + struct.pack('<I', 16)
        wav_header += struct.pack('<H', 1)  # PCM format
        wav_header += struct.pack('<H', 1)  # Mono
        wav_header += struct.pack('<I', sample_rate)
        wav_header += struct.pack('<I', sample_rate * 2)  # Byte rate
        wav_header += struct.pack('<H', 2)  # Block align
        wav_header += struct.pack('<H', 16)  # Bits per sample
        wav_header += b'data' + struct.pack('<I', num_samples * 2)
        
        # Generate some dummy audio (sine wave for testing)
        import math
        audio_data = bytearray()
        for i in range(num_samples):
            # Generate a 440Hz sine wave
            value = int(32767 * 0.5 * math.sin(2 * math.pi * 440 * i / sample_rate))
            audio_data.extend(struct.pack('<h', value))
        
        return wav_header + bytes(audio_data)
    
    async def play_audio(self, call_id: str, audio_data: bytes) -> bool:
        """
        Play audio data to a call.
        
        Args:
            call_id: ID of the call
            audio_data: Audio data in bytes to play
            
        Returns:
            True if audio was played successfully
        """
        # In a real implementation, this would stream audio to the LiveKit call
        
        # Get the participant for this call
        async with self._lock:
            call_info = self._active_calls.get(call_id)
            if not call_info or not call_info.participant_id:
                logger.warning(f"No participant for call {call_id}")
                return False
            participant_id = call_info.participant_id
        
        # Send the audio
        success = await self.send_audio(participant_id, audio_data)
        
        if success:
            logger.info(f"Played {len(audio_data)} bytes of audio to call {call_id}")
        
        return success


# Default configuration function
def get_default_config() -> VoiceGatewayConfig:
    """Get default configuration."""
    return VoiceGatewayConfig(
        livekit_host="localhost",
        livekit_port=7880,
        sip_enabled=True,
        sip_trunk_provider="twilio",
        stt_engine="whisper",
        stt_language="en",
        tts_engine="coqui",
        tts_voice="en_US/blizzard-lessac-medium",
        voice_agent_timeout_seconds=30.0,
        voice_agent_max_retries=3,
        call_recording_enabled=True,
        call_recording_storage="s3",
        call_recording_bucket="lanework-call-recordings",
        call_consent_required=True,
        target_latency_ms=800,
        max_latency_ms=1500
    )
