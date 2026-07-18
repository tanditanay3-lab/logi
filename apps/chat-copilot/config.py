"""
Configuration for the Chat Copilot.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ChatCopilotConfig(BaseModel):
    """Configuration for the Chat Copilot."""
    
    # Conversation settings
    max_conversation_history: int = Field(
        default=50,
        description="Maximum number of messages to keep in conversation history"
    )
    conversation_timeout_minutes: float = Field(
        default=30.0,
        description="Timeout for inactive conversations"
    )
    
    # Orchestrator settings
    orchestrator_url: str = Field(
        default="http://localhost:8000",
        description="URL for the Orchestrator"
    )
    conversation_router_endpoint: str = Field(
        default="/conversation",
        description="Endpoint for the Conversation Router"
    )
    
    # Response settings
    typing_indicator_enabled: bool = Field(
        default=True,
        description="Whether to show typing indicators"
    )
    response_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout for waiting for agent response"
    )
    
    # Welcome message
    welcome_message: str = Field(
        default="Hello! I'm Lanework's Chat Copilot. How can I help you today?",
        description="Welcome message for new conversations"
    )
    
    # Suggested prompts
    suggested_prompts: List[str] = Field(
        default_factory=lambda: [
            "Where is my shipment with tracking number 1234567890?",
            "What's the status of route ROUTE-001?",
            "Check inventory levels for SKU-001",
            "Optimize my delivery routes for tomorrow",
            "Report a road closure on my current route",
        ],
        description="Suggested prompts for users"
    )
    
    # Rate limiting
    rate_limit_messages_per_minute: int = Field(
        default=100,
        description="Rate limit for messages per minute"
    )


class Settings(BaseSettings):
    """Environment-based settings for the Chat Copilot."""
    
    # Service configuration
    agent_name: str = "chat-copilot"
    agent_version: str = "1.0.0"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8010
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
    
    # Observability
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    
    class Config:
        env_file = ".env"
        env_prefix = "CHAT_COPILOT_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> ChatCopilotConfig:
    """Get default configuration for the Chat Copilot."""
    return ChatCopilotConfig(
        max_conversation_history=50,
        conversation_timeout_minutes=30.0,
        orchestrator_url="http://localhost:8000",
        conversation_router_endpoint="/conversation",
        typing_indicator_enabled=True,
        response_timeout_seconds=30.0,
        welcome_message="Hello! I'm Lanework's Chat Copilot. How can I help you today?",
        rate_limit_messages_per_minute=100
    )
