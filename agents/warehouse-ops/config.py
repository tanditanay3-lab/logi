"""
Configuration for the Warehouse Operations Agent.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from packages.shared_types.schemas import TrustLevel


class WarehouseOpsConfig(BaseModel):
    """Configuration for Warehouse Operations Agent."""
    
    # Agent behavior
    trust_level: TrustLevel = Field(
        default=TrustLevel.PROPOSE_ONLY,
        description="Default trust level for the agent"
    )
    
    # Task optimization
    max_tasks_per_worker: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum tasks to assign to a single worker"
    )
    
    balance_workload: bool = Field(
        default=True,
        description="Whether to balance workload across workers"
    )
    
    prioritize_by_due: bool = Field(
        default=True,
        description="Whether to prioritize tasks by due date"
    )
    
    # Labor forecasting
    forecast_horizon_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to forecast ahead"
    )
    
    historical_data_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of historical days to use for forecasting"
    )
    
    # Dock scheduling
    default_slot_duration_minutes: int = Field(
        default=60,
        ge=15,
        le=480,
        description="Default duration for dock slots in minutes"
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
    """Environment settings for Warehouse Operations Agent."""
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8004, env="API_PORT")
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


def get_default_config() -> WarehouseOpsConfig:
    """Get default configuration for Warehouse Operations Agent."""
    return WarehouseOpsConfig(
        trust_level=TrustLevel.PROPOSE_ONLY,
        max_tasks_per_worker=20,
        balance_workload=True,
        prioritize_by_due=True,
        forecast_horizon_days=7,
        historical_data_days=30,
        default_slot_duration_minutes=60,
        auto_approval_thresholds={},
        notification_settings={},
        integration_settings={},
        agent_specific=None
    )


# Global settings instance
settings = Settings()
