"""
Configuration for the Shipment Tracking Agent.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from packages.shared_types.schemas import Config, TrustLevel


class ShipmentTrackingConfig(Config):
    """
    Configuration specific to the Shipment Tracking Agent.
    
    Inherits from the base Config and adds shipment-specific settings.
    """
    # Carrier-specific configurations
    carrier_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Configuration for each carrier"
    )
    
    # ETA drift detection settings
    eta_drift_threshold_minutes: float = Field(
        default=30.0,
        description="Threshold in minutes for ETA drift detection"
    )
    eta_drift_check_interval_minutes: float = Field(
        default=60.0,
        description="Interval in minutes for checking ETA drift"
    )
    
    # Webhook settings
    webhook_secret: Optional[str] = Field(
        default=None,
        description="Secret for verifying carrier webhooks"
    )
    webhook_enabled: bool = Field(
        default=True,
        description="Whether to accept carrier webhooks"
    )
    
    # Tracking refresh settings
    auto_refresh_enabled: bool = Field(
        default=True,
        description="Whether to automatically refresh tracking data"
    )
    auto_refresh_interval_hours: float = Field(
        default=4.0,
        description="Interval in hours for automatic tracking refresh"
    )
    
    # Notification settings for delays
    notify_on_delay: bool = Field(
        default=True,
        description="Whether to notify on detected delays"
    )
    delay_notification_threshold_minutes: float = Field(
        default=60.0,
        description="Threshold in minutes for delay notifications"
    )
    
    # Supported carriers
    supported_carriers: List[str] = Field(
        default_factory=lambda: [
            "FedEx",
            "UPS", 
            "USPS",
            "DHL",
            "Amazon Logistics",
            "OnTrac",
            "LaserShip",
        ],
        description="List of supported carriers"
    )


class Settings(BaseSettings):
    """Environment-based settings for the Shipment Tracking Agent."""
    
    # Agent configuration
    agent_name: str = "shipment-tracking"
    agent_version: str = "1.0.0"
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/lanework",
        description="Database connection URL"
    )
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8001
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
    
    # Trust level (can be overridden per-tenant)
    trust_level: TrustLevel = TrustLevel.PROPOSE_ONLY
    
    # Tool Bus
    tool_bus_url: str = "http://localhost:8000"
    
    # Observability
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    
    class Config:
        env_file = ".env"
        env_prefix = "SHIPMENT_TRACKING_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> ShipmentTrackingConfig:
    """Get default configuration for the agent."""
    return ShipmentTrackingConfig(
        trust_level=settings.trust_level,
        eta_drift_threshold_minutes=30.0,
        eta_drift_check_interval_minutes=60.0,
        webhook_enabled=True,
        auto_refresh_enabled=True,
        auto_refresh_interval_hours=4.0,
        notify_on_delay=True,
        delay_notification_threshold_minutes=60.0,
    )
