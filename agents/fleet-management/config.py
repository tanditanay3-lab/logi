"""
Configuration for the Fleet & Driver Management Agent.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from packages.shared_types.schemas import TrustLevel


class FleetManagementConfig(BaseModel):
    """Configuration for Fleet & Driver Management Agent."""
    
    # Agent behavior
    trust_level: TrustLevel = Field(
        default=TrustLevel.PROPOSE_ONLY,
        description="Default trust level for the agent"
    )
    
    # HOS compliance
    max_duty_hours: float = Field(
        default=14.0,
        ge=1.0,
        le=24.0,
        description="Maximum duty hours per day (FMCSA regulation)"
    )
    
    max_drive_hours: float = Field(
        default=11.0,
        ge=1.0,
        le=24.0,
        description="Maximum drive hours per day (FMCSA regulation)"
    )
    
    min_break_duration_minutes: int = Field(
        default=30,
        ge=0,
        le=1440,
        description="Minimum break duration in minutes"
    )
    
    # Maintenance
    maintenance_warning_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days before maintenance is due to trigger warning"
    )
    
    maintenance_overdue_days: int = Field(
        default=0,
        ge=0,
        le=30,
        description="Days after maintenance is due to trigger overdue status"
    )
    
    # License expiry
    license_warning_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days before license expiry to trigger warning"
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
    """Environment settings for Fleet & Driver Management Agent."""
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8005, env="API_PORT")
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


def get_default_config() -> FleetManagementConfig:
    """Get default configuration for Fleet & Driver Management Agent."""
    return FleetManagementConfig(
        trust_level=TrustLevel.PROPOSE_ONLY,
        max_duty_hours=14.0,
        max_drive_hours=11.0,
        min_break_duration_minutes=30,
        maintenance_warning_days=7,
        maintenance_overdue_days=0,
        license_warning_days=30,
        auto_approval_thresholds={},
        notification_settings={},
        integration_settings={},
        agent_specific=None
    )


# Global settings instance
settings = Settings()
