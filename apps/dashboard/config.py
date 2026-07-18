"""
Configuration for the Dashboard.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DashboardConfig(BaseModel):
    """Configuration for the Dashboard."""
    
    # Frontend settings
    app_name: str = "Lanework Dashboard"
    app_title: str = "Lanework - Agentic Operating System for Logistics"
    app_description: str = "Multi-tenant agentic operating system for logistics companies"
    
    # Theme
    theme_primary_color: str = "#2563eb"
    theme_secondary_color: str = "#1e40af"
    theme_accent_color: str = "#3b82f6"
    theme_background_color: str = "#f8fafc"
    theme_text_color: str = "#1e293b"
    
    # API endpoints
    api_gateway_url: str = "http://localhost:8080"
    orchestrator_url: str = "http://localhost:8000"
    
    # Feature flags
    show_shipment_tracking: bool = True
    show_inventory: bool = True
    show_route_optimization: bool = True
    show_warehouse_ops: bool = True
    show_fleet_management: bool = True
    show_customer_communication: bool = True
    show_demand_forecasting: bool = True
    show_freight_procurement: bool = True
    show_voice: bool = True
    
    # Default view
    default_view: str = "dashboard"  # or "shipments", "routes", "inventory", etc.
    
    # Refresh intervals (in seconds)
    auto_refresh_interval: int = 30
    realtime_updates_enabled: bool = True
    
    # Pagination
    default_page_size: int = 25
    max_page_size: int = 100
    
    # Notifications
    notifications_enabled: bool = True
    notification_duration: int = 5000  # milliseconds
    
    # Maps
    maps_provider: str = "google"  # or "mapbox", "leaflet"
    maps_api_key: Optional[str] = None


class Settings(BaseSettings):
    """Environment-based settings for the Dashboard."""
    
    # Service configuration
    agent_name: str = "dashboard"
    agent_version: str = "1.0.0"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 3000
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
        env_prefix = "DASHBOARD_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> DashboardConfig:
    """Get default configuration for the Dashboard."""
    return DashboardConfig(
        app_name="Lanework Dashboard",
        app_title="Lanework - Agentic Operating System for Logistics",
        app_description="Multi-tenant agentic operating system for logistics companies",
        theme_primary_color="#2563eb",
        theme_secondary_color="#1e40af",
        theme_accent_color="#3b82f6",
        theme_background_color="#f8fafc",
        theme_text_color="#1e293b",
        api_gateway_url="http://localhost:8080",
        orchestrator_url="http://localhost:8000",
        show_shipment_tracking=True,
        show_inventory=True,
        show_route_optimization=True,
        show_warehouse_ops=True,
        show_fleet_management=True,
        show_customer_communication=True,
        show_demand_forecasting=True,
        show_freight_procurement=True,
        show_voice=True,
        default_view="dashboard",
        auto_refresh_interval=30,
        realtime_updates_enabled=True,
        default_page_size=25,
        max_page_size=100,
        notifications_enabled=True,
        notification_duration=5000,
        maps_provider="google"
    )
