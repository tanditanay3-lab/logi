"""
Configuration for the Route Optimization Agent.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from packages.shared_types.schemas import Config, TrustLevel


class RouteOptimizationConfig(Config):
    """
    Configuration specific to the Route Optimization Agent.
    
    Inherits from the base Config and adds route-specific settings.
    """
    # Optimization settings
    optimization_algorithm: str = Field(
        default="genetic",
        description="Optimization algorithm to use (genetic, simulated_annealing, greedy)"
    )
    optimization_iterations: int = Field(
        default=1000,
        description="Number of iterations for optimization"
    )
    optimization_population_size: int = Field(
        default=100,
        description="Population size for genetic algorithm"
    )
    optimization_mutation_rate: float = Field(
        default=0.1,
        description="Mutation rate for genetic algorithm"
    )
    
    # Constraints
    max_route_duration_hours: float = Field(
        default=12.0,
        description="Maximum route duration in hours"
    )
    max_route_distance_miles: float = Field(
        default=500.0,
        description="Maximum route distance in miles"
    )
    max_stops_per_route: int = Field(
        default=20,
        description="Maximum stops per route"
    )
    
    # Driver/Fleet integration (stubbed for Phase 1)
    fleet_management_enabled: bool = Field(
        default=False,
        description="Whether to integrate with Fleet Management Agent (stubbed in Phase 1)"
    )
    fleet_management_agent_url: str = Field(
        default="http://fleet-management:8005",
        description="URL for Fleet Management Agent"
    )
    check_hos_compliance: bool = Field(
        default=False,
        description="Whether to check HOS compliance before assigning (stubbed in Phase 1)"
    )
    
    # Traffic and weather
    traffic_enabled: bool = Field(
        default=False,
        description="Whether to consider traffic in optimization"
    )
    weather_enabled: bool = Field(
        default=False,
        description="Whether to consider weather in optimization"
    )
    
    # Re-optimization settings
    reoptimization_enabled: bool = Field(
        default=True,
        description="Whether to allow route re-optimization"
    )
    reoptimization_triggers: List[str] = Field(
        default_factory=lambda: ["delay", "driver_issue", "traffic", "weather"],
        description="Triggers for automatic re-optimization"
    )
    reoptimization_cooldown_minutes: float = Field(
        default=30.0,
        description="Cooldown period between re-optimizations"
    )
    
    # Cost calculations
    fuel_cost_per_gallon: float = Field(
        default=3.50,
        description="Fuel cost per gallon"
    )
    driver_cost_per_hour: float = Field(
        default=25.00,
        description="Driver cost per hour"
    )
    vehicle_cost_per_mile: float = Field(
        default=1.50,
        description="Vehicle cost per mile"
    )
    
    # Time window settings
    default_time_window_start: str = Field(
        default="08:00:00",
        description="Default time window start"
    )
    default_time_window_end: str = Field(
        default="17:00:00",
        description="Default time window end"
    )
    time_window_penalty_weight: float = Field(
        default=10.0,
        description="Weight for time window violations in optimization"
    )
    
    # Capacity settings
    default_vehicle_capacity_cubic_feet: float = Field(
        default=1000.0,
        description="Default vehicle capacity in cubic feet"
    )
    default_vehicle_capacity_weight_lbs: float = Field(
        default=10000.0,
        description="Default vehicle capacity in pounds"
    )
    capacity_penalty_weight: float = Field(
        default=100.0,
        description="Weight for capacity violations in optimization"
    )


class Settings(BaseSettings):
    """Environment-based settings for the Route Optimization Agent."""
    
    # Agent configuration
    agent_name: str = "route-optimization"
    agent_version: str = "1.0.0"
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/lanework",
        description="Database connection URL"
    )
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8003
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
        env_prefix = "ROUTE_OPTIMIZATION_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> RouteOptimizationConfig:
    """Get default configuration for the agent."""
    return RouteOptimizationConfig(
        trust_level=settings.trust_level,
        optimization_algorithm="genetic",
        optimization_iterations=1000,
        optimization_population_size=100,
        optimization_mutation_rate=0.1,
        max_route_duration_hours=12.0,
        max_route_distance_miles=500.0,
        max_stops_per_route=20,
        fleet_management_enabled=False,
        check_hos_compliance=False,
        traffic_enabled=False,
        weather_enabled=False,
        reoptimization_enabled=True,
        reoptimization_triggers=["delay", "driver_issue", "traffic", "weather"],
        reoptimization_cooldown_minutes=30.0,
        fuel_cost_per_gallon=3.50,
        driver_cost_per_hour=25.00,
        vehicle_cost_per_mile=1.50,
        default_time_window_start="08:00:00",
        default_time_window_end="17:00:00",
        time_window_penalty_weight=10.0,
        default_vehicle_capacity_cubic_feet=1000.0,
        default_vehicle_capacity_weight_lbs=10000.0,
        capacity_penalty_weight=100.0
    )
