"""
Configuration for the Inventory Management Agent.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from packages.shared_types.schemas import Config, TrustLevel


class InventoryManagementConfig(Config):
    """
    Configuration specific to the Inventory Management Agent.
    
    Inherits from the base Config and adds inventory-specific settings.
    """
    # Replenishment settings
    replenishment_enabled: bool = Field(
        default=True,
        description="Whether to generate replenishment recommendations"
    )
    replenishment_check_interval_hours: float = Field(
        default=24.0,
        description="Interval in hours for checking replenishment needs"
    )
    replenishment_horizon_days: int = Field(
        default=30,
        description="Forecast horizon for replenishment calculations"
    )
    
    # Low stock settings
    low_stock_threshold_pct: float = Field(
        default=20.0,
        description="Percentage threshold for low stock alerts"
    )
    low_stock_check_interval_hours: float = Field(
        default=1.0,
        description="Interval in hours for checking low stock"
    )
    notify_on_low_stock: bool = Field(
        default=True,
        description="Whether to notify on low stock"
    )
    
    # Discrepancy settings
    discrepancy_detection_enabled: bool = Field(
        default=True,
        description="Whether to detect discrepancies"
    )
    discrepancy_threshold_pct: float = Field(
        default=5.0,
        description="Percentage threshold for discrepancy detection"
    )
    
    # Demand forecasting integration (stub for Phase 1)
    demand_forecasting_enabled: bool = Field(
        default=False,
        description="Whether to use demand forecasting (stubbed in Phase 1)"
    )
    demand_forecasting_agent_url: str = Field(
        default="http://demand-forecasting:8007",
        description="URL for demand forecasting agent"
    )
    
    # Warehouse settings
    default_warehouse_id: Optional[str] = Field(
        default=None,
        description="Default warehouse ID"
    )
    
    # Inventory adjustment limits
    max_adjustment_pct: float = Field(
        default=10.0,
        description="Maximum percentage adjustment without approval"
    )
    max_adjustment_value: float = Field(
        default=1000.00,
        description="Maximum value adjustment without approval"
    )


class Settings(BaseSettings):
    """Environment-based settings for the Inventory Management Agent."""
    
    # Agent configuration
    agent_name: str = "inventory-management"
    agent_version: str = "1.0.0"
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/lanework",
        description="Database connection URL"
    )
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8002
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
        env_prefix = "INVENTORY_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> InventoryManagementConfig:
    """Get default configuration for the agent."""
    return InventoryManagementConfig(
        trust_level=settings.trust_level,
        replenishment_enabled=True,
        replenishment_check_interval_hours=24.0,
        replenishment_horizon_days=30,
        low_stock_threshold_pct=20.0,
        low_stock_check_interval_hours=1.0,
        notify_on_low_stock=True,
        discrepancy_detection_enabled=True,
        discrepancy_threshold_pct=5.0,
        demand_forecasting_enabled=False,
        max_adjustment_pct=10.0,
        max_adjustment_value=1000.00
    )
