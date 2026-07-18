"""
Configuration for the Voice Gateway.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class VoiceGatewayConfig(BaseModel):
    """Configuration for the Voice Gateway."""
    
    # LiveKit configuration
    livekit_host: str = "localhost"
    livekit_port: int = 7880
    livekit_api_key: Optional[str] = None
    livekit_api_secret: Optional[str] = None
    livekit_room_name: str = "lanework-voice"
    
    # SIP configuration
    sip_enabled: bool = True
    sip_trunk_provider: str = "twilio"  # or "vonage", "telnyx", etc.
    sip_trunk_credentials: Dict[str, str] = Field(
        default_factory=dict,
        description="SIP trunk credentials"
    )
    sip_phone_number: Optional[str] = None
    
    # STT/TTS configuration
    stt_engine: str = "whisper"  # or "google", "aws", "azure"
    stt_language: str = "en"
    tts_engine: str = "coqui"  # or "google", "aws", "azure"
    tts_voice: str = "en_US/blizzard-lessac-medium"
    
    # Voice Agent configuration
    voice_agent_timeout_seconds: float = 30.0
    voice_agent_max_retries: int = 3
    
    # Call recording
    call_recording_enabled: bool = True
    call_recording_storage: str = "s3"  # or "local", "gcs"
    call_recording_bucket: str = "lanework-call-recordings"
    
    # Consent
    call_consent_required: bool = True
    call_consent_message: str = "This call may be recorded for quality assurance. Press 1 to consent."
    
    # Latency optimization
    target_latency_ms: int = 800  # Target turn-taking latency
    max_latency_ms: int = 1500  # Maximum acceptable latency


class Settings(BaseSettings):
    """Environment-based settings for the Voice Gateway."""
    
    # Service configuration
    agent_name: str = "voice-gateway"
    agent_version: str = "1.0.0"
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/lanework",
        description="Database connection URL"
    )
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8009
    api_debug: bool = False
    
    # Authentication
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication"
    )
    
    # Tenant
    tenant_id: Optional[str] = Field(
        default=None,
        description="Default tenant ID for single-tenant mode"
    )
    
    # Orchestrator
    orchestrator_url: str = "http://localhost:8000"
    
    # Observability
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    
    class Config:
        env_file = ".env"
        env_prefix = "VOICE_GATEWAY_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> VoiceGatewayConfig:
    """Get default configuration for the Voice Gateway."""
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
