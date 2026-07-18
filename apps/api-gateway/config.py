"""
Configuration for the API Gateway.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class APIGatewayConfig(BaseModel):
    """Configuration for the API Gateway."""
    
    # Service endpoints
    orchestrator_host: str = "localhost"
    orchestrator_port: int = 8000
    
    shipment_tracking_host: str = "localhost"
    shipment_tracking_port: int = 8001
    
    inventory_host: str = "localhost"
    inventory_port: int = 8002
    
    route_optimization_host: str = "localhost"
    route_optimization_port: int = 8003
    
    warehouse_ops_host: str = "localhost"
    warehouse_ops_port: int = 8004
    
    fleet_management_host: str = "localhost"
    fleet_management_port: int = 8005
    
    customer_communication_host: str = "localhost"
    customer_communication_port: int = 8006
    
    demand_forecasting_host: str = "localhost"
    demand_forecasting_port: int = 8007
    
    freight_procurement_host: str = "localhost"
    freight_procurement_port: int = 8008
    
    voice_host: str = "localhost"
    voice_port: int = 8009
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 100
    rate_limit_burst_size: int = 20
    
    # Authentication
    auth_enabled: bool = True
    api_key: Optional[str] = None
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    
    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins"
    )
    cors_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        description="Allowed CORS methods"
    )
    cors_headers: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS headers"
    )
    
    # Logging
    log_level: str = "info"
    log_format: str = "json"
    
    # Request ID
    request_id_header: str = "X-Request-ID"
    
    # Tenant
    tenant_header: str = "X-Tenant-ID"
    default_tenant_id: Optional[str] = None


class Settings(BaseSettings):
    """Environment-based settings for the API Gateway."""
    
    # Service configuration
    agent_name: str = "api-gateway"
    agent_version: str = "1.0.0"
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/lanework",
        description="Database connection URL"
    )
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
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
        env_prefix = "API_GATEWAY_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> APIGatewayConfig:
    """Get default configuration for the API Gateway."""
    return APIGatewayConfig(
        orchestrator_host="localhost",
        orchestrator_port=8000,
        shipment_tracking_host="localhost",
        shipment_tracking_port=8001,
        inventory_host="localhost",
        inventory_port=8002,
        route_optimization_host="localhost",
        route_optimization_port=8003,
        warehouse_ops_host="localhost",
        warehouse_ops_port=8004,
        fleet_management_host="localhost",
        fleet_management_port=8005,
        customer_communication_host="localhost",
        customer_communication_port=8006,
        demand_forecasting_host="localhost",
        demand_forecasting_port=8007,
        freight_procurement_host="localhost",
        freight_procurement_port=8008,
        voice_host="localhost",
        voice_port=8009,
        rate_limit_enabled=True,
        rate_limit_requests_per_minute=100,
        rate_limit_burst_size=20,
        auth_enabled=True,
        cors_origins=["*"],
        cors_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        cors_headers=["*"],
        log_level="info",
        log_format="json"
    )
