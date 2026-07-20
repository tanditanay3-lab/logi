"""
SQLAlchemy models for Lanework SaaS layer.

All models include org_id for row-level security (RLS).
The agent platform expects tenant_id in format: tenant_<uuid>
"""

import enum
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Date,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as SQLUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================

class SubscriptionStatus(str, enum.Enum):
    """Status of a subscription."""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INACTIVE = "inactive"


class PlanInterval(str, enum.Enum):
    """Billing interval for plans."""
    MONTHLY = "monthly"
    YEARLY = "yearly"
    QUARTERLY = "quarterly"


class UsageType(str, enum.Enum):
    """Type of usage being metered."""
    AGENT_TASKS = "agent_tasks"
    API_CALLS = "api_calls"
    STORAGE_GB = "storage_gb"
    VOICE_MINUTES = "voice_minutes"
    SHIPMENTS_TRACKED = "shipments_tracked"
    ROUTES_OPTIMIZED = "routes_optimized"
    INVENTORY_ITEMS = "inventory_items"


class UserRole(str, enum.Enum):
    """Roles for SaaS users."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class UserStatus(str, enum.Enum):
    """Status of a SaaS user."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# ============================================================================
# Mixins
# ============================================================================

class OrgMixin:
    """Mixin for organization-specific models."""
    org_id = Column(String(64), nullable=False, index=True)


class TimestampMixin:
    """Mixin for models with timestamps."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)


# ============================================================================
# SaaS Core Models
# ============================================================================

class Organization(TimestampMixin, Base):
    """
    Organization model - the tenant in the SaaS layer.
    
    This maps to the agent platform's Tenant model.
    The agent platform expects tenant_id in format: tenant_<uuid>
    We'll use org_id as the primary identifier here, and map it to tenant_id
    when calling the agent platform.
    """
    __tablename__ = "organizations"
    
    id = Column(String(64), primary_key=True, default=lambda: f"org_{str(uuid4())[:8]}")
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False)
    status = Column(String(32), default="active")
    
    # Billing info (for future Stripe integration)
    stripe_customer_id = Column(String(255))
    default_payment_method_id = Column(String(255))
    
    # Plan subscription
    current_plan_id = Column(String(64), ForeignKey('plans.id'))
    
    # Usage tracking
    current_usage_period_start = Column(DateTime(timezone=True))
    current_usage_period_end = Column(DateTime(timezone=True))
    
    # Settings
    config = Column(JSONB, default={})
    
    # Relationships
    users = relationship("SaasUser", backref="organization")
    subscriptions = relationship("Subscription", backref="organization")
    usage_records = relationship("UsageRecord", backref="organization")
    
    __table_args__ = (
        Index('ix_organization_slug', 'slug', unique=True),
        Index('ix_organization_status', 'status'),
    )
    
    @property
    def tenant_id(self) -> str:
        """Get the tenant_id format expected by the agent platform."""
        # Extract the UUID part from org_<uuid> and format as tenant_<uuid>
        if self.id.startswith("org_"):
            uuid_part = self.id[4:]
            return f"tenant_{uuid_part}"
        return f"tenant_{self.id}"


class Plan(TimestampMixin, Base):
    """
    Plan model - defines the pricing tiers and features.
    """
    __tablename__ = "plans"
    
    id = Column(String(64), primary_key=True, default=lambda: f"plan_{str(uuid4())[:8]}")
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    interval = Column(Enum(PlanInterval), default=PlanInterval.MONTHLY)
    trial_period_days = Column(Integer, default=14)
    
    # Limits
    max_agent_tasks_per_month = Column(Integer, default=10000)
    max_api_calls_per_month = Column(Integer, default=100000)
    max_storage_gb = Column(Integer, default=100)
    max_voice_minutes_per_month = Column(Integer, default=1000)
    max_shipments_tracked = Column(Integer, default=10000)
    max_routes_optimized = Column(Integer, default=5000)
    max_inventory_items = Column(Integer, default=50000)
    
    # Feature flags
    features = Column(JSONB, default={})
    
    # Stripe price ID (for future integration)
    stripe_price_id = Column(String(255))
    
    # Sort order
    sort_order = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    subscriptions = relationship("Subscription", backref="plan")
    organizations = relationship("Organization", backref="plan")
    
    __table_args__ = (
        Index('ix_plan_name', 'name', unique=True),
        Index('ix_plan_is_active', 'is_active'),
    )


class Subscription(TimestampMixin, Base):
    """
    Subscription model - tracks an organization's subscription to a plan.
    
    This is a mirror of Stripe subscription state (for future integration).
    """
    __tablename__ = "subscriptions"
    
    id = Column(String(64), primary_key=True, default=lambda: f"sub_{str(uuid4())[:8]}")
    org_id = Column(String(64), ForeignKey('organizations.id'), nullable=False, index=True)
    plan_id = Column(String(64), ForeignKey('plans.id'), nullable=False, index=True)
    
    # Stripe IDs (for future integration)
    stripe_subscription_id = Column(String(255))
    stripe_invoice_id = Column(String(255))
    
    # Status
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, index=True)
    
    # Timing
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    cancel_at_period_end = Column(Boolean, default=False)
    canceled_at = Column(DateTime(timezone=True))
    trial_start = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True))
    
    # Billing
    amount_due = Column(Numeric(10, 2))
    amount_paid = Column(Numeric(10, 2))
    amount_remaining = Column(Numeric(10, 2))
    
    # Usage
    usage_agent_tasks = Column(Integer, default=0)
    usage_api_calls = Column(Integer, default=0)
    usage_storage_gb = Column(Integer, default=0)
    usage_voice_minutes = Column(Integer, default=0)
    usage_shipments_tracked = Column(Integer, default=0)
    usage_routes_optimized = Column(Integer, default=0)
    usage_inventory_items = Column(Integer, default=0)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[org_id])
    plan = relationship("Plan", foreign_keys=[plan_id])
    usage_records = relationship("UsageRecord", backref="subscription")
    
    __table_args__ = (
        Index('ix_subscription_org', 'org_id'),
        Index('ix_subscription_status', 'status'),
        Index('ix_subscription_period', 'current_period_start', 'current_period_end'),
    )


class UsageRecord(TimestampMixin, Base):
    """
    UsageRecord model - tracks usage for metering and billing.
    
    Must be idempotent - dedupe by event_id.
    """
    __tablename__ = "usage_records"
    
    id = Column(String(64), primary_key=True, default=lambda: f"usage_{str(uuid4())[:8]}")
    org_id = Column(String(64), ForeignKey('organizations.id'), nullable=False, index=True)
    subscription_id = Column(String(64), ForeignKey('subscriptions.id'), index=True)
    
    # Event info for idempotency
    event_id = Column(String(255), nullable=False, index=True)
    event_type = Column(String(255))
    event_source = Column(String(255))  # e.g., "agent-platform", "api-gateway"
    
    # Usage type
    usage_type = Column(Enum(UsageType), nullable=False, index=True)
    
    # Amount
    amount = Column(Integer, nullable=False)
    
    # Context
    agent_task_id = Column(String(64))
    agent_type = Column(String(64))
    metadata = Column(JSONB, default={})
    
    # Period
    period_start = Column(DateTime(timezone=True))
    period_end = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[org_id])
    subscription = relationship("Subscription", foreign_keys=[subscription_id])
    
    __table_args__ = (
        Index('ix_usage_record_org_type', 'org_id', 'usage_type'),
        Index('ix_usage_record_event_id', 'event_id', unique=True),  # For idempotency
        Index('ix_usage_record_period', 'period_start', 'period_end'),
        Index('ix_usage_record_subscription', 'subscription_id'),
    )


class SaasUser(TimestampMixin, Base):
    """
    SaaS User model - users who can log into the SaaS dashboard.
    
    Uses Neon Auth for authentication.
    """
    __tablename__ = "saas_users"
    
    id = Column(String(64), primary_key=True, default=lambda: f"saas_user_{str(uuid4())[:8]}")
    org_id = Column(String(64), ForeignKey('organizations.id'), nullable=False, index=True)
    
    # Neon Auth user ID
    neon_auth_user_id = Column(String(255), unique=True, nullable=False)
    
    # User info
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    avatar_url = Column(String(512))
    
    # Role
    role = Column(Enum(UserRole), default=UserRole.MEMBER)
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    
    # Preferences
    preferences = Column(JSONB, default={})
    
    # Last login
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[org_id])
    
    __table_args__ = (
        Index('ix_saas_user_org_email', 'org_id', 'email', unique=True),
        Index('ix_saas_user_neon_auth', 'neon_auth_user_id', unique=True),
        Index('ix_saas_user_status', 'status'),
    )


# ============================================================================
# RLS Policies Setup
# ============================================================================

def get_rls_policies():
    """
    Get RLS policies for all SaaS tables.
    
    These should be applied to the database to enforce tenant isolation.
    """
    return {
        "organizations": [
            "CREATE POLICY org_access_policy ON organizations FOR ALL USING (true)",
        ],
        "plans": [
            "CREATE POLICY plan_access_policy ON plans FOR ALL USING (true)",
        ],
        "subscriptions": [
            "CREATE POLICY sub_access_policy ON subscriptions FOR ALL USING (org_id = current_setting('app.current_org_id'))",
        ],
        "usage_records": [
            "CREATE POLICY usage_access_policy ON usage_records FOR ALL USING (org_id = current_setting('app.current_org_id'))",
        ],
        "saas_users": [
            "CREATE POLICY user_access_policy ON saas_users FOR ALL USING (org_id = current_setting('app.current_org_id'))",
        ],
    }


def get_rls_setup_sql():
    """Get SQL to set up RLS for all SaaS tables."""
    sql_statements = []
    
    # Enable RLS on each table
    tables_with_org = ["subscriptions", "usage_records", "saas_users"]
    
    for table in tables_with_org:
        sql_statements.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        sql_statements.append(
            f"CREATE POLICY {table}_org_policy ON {table} "
            f"FOR ALL USING (org_id = current_setting('app.current_org_id'))"
        )
    
    # For organizations and plans, allow all access (they're global)
    sql_statements.append("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;")
    sql_statements.append("CREATE POLICY org_all_policy ON organizations FOR ALL USING (true)")
    
    sql_statements.append("ALTER TABLE plans ENABLE ROW LEVEL SECURITY;")
    sql_statements.append("CREATE POLICY plan_all_policy ON plans FOR ALL USING (true)")
    
    return "\n".join(sql_statements)
