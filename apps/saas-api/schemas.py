"""
Pydantic schemas for Saas-api.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr


# ============================================================================
# Organization
# ============================================================================

class OrganizationBase(BaseModel):
    """Base schema for Organization."""
    name: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, max_length=64)


class OrganizationCreate(OrganizationBase):
    """Schema for creating an Organization."""
    pass


class OrganizationResponse(OrganizationBase):
    """Response schema for Organization."""
    id: str
    status: str
    current_plan_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """List response for Organizations."""
    organizations: List[OrganizationResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Plan
# ============================================================================

class PlanBase(BaseModel):
    """Base schema for Plan."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    price: float = Field(..., gt=0)
    interval: str = Field(default="monthly")  # monthly, yearly, quarterly
    trial_period_days: int = Field(default=14, ge=0)


class PlanCreate(PlanBase):
    """Schema for creating a Plan."""
    max_agent_tasks_per_month: int = Field(default=10000, ge=0)
    max_api_calls_per_month: int = Field(default=100000, ge=0)
    max_storage_gb: int = Field(default=100, ge=0)
    max_voice_minutes_per_month: int = Field(default=1000, ge=0)
    max_shipments_tracked: int = Field(default=10000, ge=0)
    max_routes_optimized: int = Field(default=5000, ge=0)
    max_inventory_items: int = Field(default=50000, ge=0)
    features: Dict[str, Any] = Field(default_factory=dict)
    stripe_price_id: Optional[str] = Field(default=None)
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)


class PlanResponse(PlanBase):
    """Response schema for Plan."""
    id: str
    max_agent_tasks_per_month: int
    max_api_calls_per_month: int
    max_storage_gb: int
    max_voice_minutes_per_month: int
    max_shipments_tracked: int
    max_routes_optimized: int
    max_inventory_items: int
    features: Dict[str, Any]
    stripe_price_id: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PlanListResponse(BaseModel):
    """List response for Plans."""
    plans: List[PlanResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# User
# ============================================================================

class UserBase(BaseModel):
    """Base schema for SaaS User."""
    email: EmailStr = Field(..., max_length=255)
    name: Optional[str] = Field(default=None, max_length=255)


class UserCreate(UserBase):
    """Schema for creating a User."""
    password: str = Field(..., min_length=8)
    role: str = Field(default="member")  # owner, admin, member, viewer


class UserResponse(UserBase):
    """Response schema for User."""
    id: str
    org_id: str
    neon_auth_user_id: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    status: str
    preferences: Dict[str, Any] = Field(default_factory=dict)
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """List response for Users."""
    users: List[UserResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Authentication
# ============================================================================

class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


# ============================================================================
# Neon Auth
# ============================================================================

class NeonAuthUser(BaseModel):
    """Schema for Neon Auth user."""
    id: str
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class NeonAuthToken(BaseModel):
    """Schema for Neon Auth token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================================================================
# Subscription (stub for now)
# ============================================================================

class SubscriptionBase(BaseModel):
    """Base schema for Subscription."""
    plan_id: str


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a Subscription."""
    pass


class SubscriptionResponse(SubscriptionBase):
    """Response schema for Subscription."""
    id: str
    org_id: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Usage Record (stub for now)
# ============================================================================

class UsageRecordBase(BaseModel):
    """Base schema for UsageRecord."""
    usage_type: str
    amount: int = Field(..., ge=0)


class UsageRecordCreate(UsageRecordBase):
    """Schema for creating a UsageRecord."""
    event_id: str
    event_type: Optional[str] = None
    event_source: Optional[str] = None
    agent_task_id: Optional[str] = None
    agent_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UsageRecordResponse(UsageRecordBase):
    """Response schema for UsageRecord."""
    id: str
    org_id: str
    subscription_id: Optional[str] = None
    event_id: str
    event_type: Optional[str] = None
    event_source: Optional[str] = None
    agent_task_id: Optional[str] = None
    agent_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Error
# ============================================================================

class ErrorResponse(BaseModel):
    """Schema for error response."""
    error: Dict[str, Any] = Field(..., description="Error details")
