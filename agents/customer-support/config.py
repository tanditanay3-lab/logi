"""
Configuration for the Customer Communication Agent.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from packages.shared_types.schemas import TrustLevel


class CustomerSupportConfig(BaseModel):
    """Configuration for Customer Communication Agent."""
    
    # Agent behavior
    trust_level: TrustLevel = Field(
        default=TrustLevel.PROPOSE_ONLY,
        description="Default trust level for the agent"
    )
    
    # Sentiment analysis
    sentiment_negative_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Threshold for negative sentiment detection"
    )
    
    sentiment_positive_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold for positive sentiment detection"
    )
    
    # Escalation
    auto_escalate_negative_sentiment: bool = Field(
        default=True,
        description="Whether to auto-escalate negative sentiment"
    )
    
    # Notifications
    default_notification_channels: List[str] = Field(
        default_factory=lambda: ["email"],
        description="Default notification channels"
    )
    
    # Response templates
    response_templates: Dict[str, str] = Field(
        default_factory=dict,
        description="Response templates for common queries"
    )
    
    # Auto-approval thresholds
    auto_approval_thresholds: Dict[str, Any] = Field(
        default_factory=dict,
        description="Thresholds for auto-approval"
    )
    
    # Notification settings
    notification_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Notification settings"
    )
    
    # Integration settings
    integration_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Integration settings"
    )
    
    # Agent-specific configuration
    agent_specific: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Agent-specific configuration"
    )


class Settings(BaseSettings):
    """Environment settings for Customer Communication Agent."""
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8006, env="API_PORT")
    api_debug: bool = Field(default=False, env="API_DEBUG")
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/lanework",
        env="DATABASE_URL"
    )
    
    # Authentication
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    tenant_id: Optional[str] = Field(default=None, env="TENANT_ID")
    
    # Webhook
    webhook_secret: Optional[str] = Field(default=None, env="WEBHOOK_SECRET")
    
    # Logging
    log_level: str = Field(default="info", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_default_config() -> CustomerSupportConfig:
    """Get default configuration for Customer Communication Agent."""
    return CustomerSupportConfig(
        trust_level=TrustLevel.PROPOSE_ONLY,
        sentiment_negative_threshold=0.3,
        sentiment_positive_threshold=0.7,
        auto_escalate_negative_sentiment=True,
        default_notification_channels=["email"],
        response_templates={},
        auto_approval_thresholds={},
        notification_settings={},
        integration_settings={},
        agent_specific=None
    )


# Global settings instance
settings = Settings()
