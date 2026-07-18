"""
Configuration for the Orchestrator.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from packages.shared_types.schemas import TrustLevel


class OrchestratorConfig(BaseModel):
    """Configuration for the Orchestrator."""
    
    # Agent configuration
    agent_timeout_seconds: float = Field(
        default=30.0,
        description="Default timeout for agent calls"
    )
    agent_max_retries: int = Field(
        default=3,
        description="Maximum retries for agent calls"
    )
    
    # Conversation Router
    conversation_max_history: int = Field(
        default=10,
        description="Maximum conversation history to maintain"
    )
    conversation_timeout_seconds: float = Field(
        default=60.0,
        description="Timeout for conversation processing"
    )
    
    # Task Orchestrator
    task_queue_size: int = Field(
        default=1000,
        description="Maximum size of the task queue"
    )
    task_worker_count: int = Field(
        default=10,
        description="Number of task workers"
    )
    
    # Planner
    plan_max_steps: int = Field(
        default=20,
        description="Maximum number of steps in a plan"
    )
    plan_optimization_enabled: bool = Field(
        default=True,
        description="Whether to optimize plans"
    )
    
    # Guardrails
    guardrails_enabled: bool = Field(
        default=True,
        description="Whether guardrails are enabled"
    )
    guardrails_strict_mode: bool = Field(
        default=False,
        description="Whether to enforce strict guardrails (block vs warn)"
    )
    
    # Default trust level
    default_trust_level: TrustLevel = TrustLevel.PROPOSE_ONLY
    
    # Agent endpoints
    agent_endpoints: Dict[str, str] = Field(
        default_factory=lambda: {
            "shipment-tracking": "http://localhost:8001",
            "inventory": "http://localhost:8002",
            "route-optimization": "http://localhost:8003",
            "warehouse-ops": "http://localhost:8004",
            "fleet-management": "http://localhost:8005",
            "customer-communication": "http://localhost:8006",
            "demand-forecasting": "http://localhost:8007",
            "freight-procurement": "http://localhost:8008",
            "voice": "http://localhost:8009",
        },
        description="Endpoints for each agent"
    )


class Settings(BaseSettings):
    """Environment-based settings for the Orchestrator."""
    
    # Service configuration
    agent_name: str = "orchestrator"
    agent_version: str = "1.0.0"
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/lanework",
        description="Database connection URL"
    )
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
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
    
    # Tool Bus
    tool_bus_url: str = "http://localhost:8000"
    
    # Observability
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    
    class Config:
        env_file = ".env"
        env_prefix = "ORCHESTRATOR_"


# Global settings instance
settings = Settings()


# Default configuration
def get_default_config() -> OrchestratorConfig:
    """Get default configuration for the orchestrator."""
    return OrchestratorConfig(
        agent_timeout_seconds=30.0,
        agent_max_retries=3,
        conversation_max_history=10,
        conversation_timeout_seconds=60.0,
        task_queue_size=1000,
        task_worker_count=10,
        plan_max_steps=20,
        plan_optimization_enabled=True,
        guardrails_enabled=True,
        guardrails_strict_mode=False,
        default_trust_level=TrustLevel.PROPOSE_ONLY
    )
