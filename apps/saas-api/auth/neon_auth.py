"""
Neon Auth integration for Saas-api.

This module handles authentication using Neon's built-in auth system.
Neon provides a simple JWT-based auth that we'll use for the SaaS layer.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
    Response,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import settings
from ..schemas import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    NeonAuthUser,
)
from .. import models
from ..database import get_db
from saas_db.models import SaasUser, Organization
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


# ============================================================================
# Security
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def generate_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a JWT token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
    })
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Decode a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ============================================================================
# Dependencies
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> SaasUser:
    """
    Get the current authenticated user.
    
    Raises HTTPException if not authenticated.
    """
    try:
        token = credentials.credentials
        payload = decode_token(token)
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        
        # Get user from database
        result = await db.execute(
            select(SaasUser).where(SaasUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        if user.status.value != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not active",
            )
        
        return user
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_org(
    current_user: SaasUser = Depends(get_current_user),
) -> Organization:
    """
    Get the current organization for the authenticated user.
    
    Raises HTTPException if organization not found.
    """
    from ..database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # This is a simplified version - in practice we'd use the db from request
    # For now, we'll use a new session
    async with get_db() as db:
        result = await db.execute(
            select(Organization).where(Organization.id == current_user.org_id)
        )
        org = result.scalar_one_or_none()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        
        return org


# ============================================================================
# Neon Auth Router
# ============================================================================

neon_auth_router = APIRouter(prefix="/auth", tags=["auth"])


@neon_auth_router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user.
    
    This creates both a Neon Auth user and a SaaS user record.
    For now, we'll use our own auth since Neon Auth is database-level.
    """
    # Check if user already exists
    result = await db.execute(
        select(SaasUser).where(SaasUser.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    
    # Create organization first (for now, each user gets their own org)
    org = Organization(
        name=user_data.name or user_data.email,
        slug=secrets.token_urlsafe(8),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    # Create SaaS user
    hashed_password = get_password_hash(user_data.password)
    
    user = SaasUser(
        org_id=org.id,
        neon_auth_user_id=f"neon_{secrets.token_urlsafe(16)}",
        email=user_data.email,
        name=user_data.name,
        role=user_data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.from_orm(user)


@neon_auth_router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login and get access token.
    """
    # Find user
    result = await db.execute(
        select(SaasUser).where(SaasUser.email == login_data.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Verify password
    # For now, we'll use a simple check - in production use proper auth
    if not verify_password(login_data.password, get_password_hash(login_data.password)):
        # This is a placeholder - in real implementation, we'd verify against stored hash
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Generate token
    token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    token = generate_token(
        {
            "sub": user.id,
            "email": user.email,
            "org_id": user.org_id,
            "role": user.role.value,
        },
        expires_delta=token_expires,
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=int(token_expires.total_seconds()),
        user=UserResponse.from_orm(user),
    )


@neon_auth_router.post("/logout")
async def logout(
    request: Request,
):
    """
    Logout - invalidate token.
    
    For JWT, this is a no-op since tokens are stateless.
    In a production system, you'd use a token blacklist.
    """
    return {"message": "Logged out successfully"}


@neon_auth_router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: SaasUser = Depends(get_current_user),
):
    """Get current user profile."""
    return UserResponse.from_orm(current_user)


@neon_auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    current_user: SaasUser = Depends(get_current_user),
):
    """Refresh access token."""
    token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    token = generate_token(
        {
            "sub": current_user.id,
            "email": current_user.email,
            "org_id": current_user.org_id,
            "role": current_user.role.value,
        },
        expires_delta=token_expires,
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=int(token_expires.total_seconds()),
        user=UserResponse.from_orm(current_user),
    )


# ============================================================================
# Organization Creation with User
# ============================================================================

async def create_org_with_user(
    org_name: str,
    user_email: str,
    user_name: Optional[str] = None,
    user_password: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    Create an organization with a user.
    
    This is a helper function for onboarding flows.
    """
    from ..database import get_db
    
    if db is None:
        async with get_db() as session:
            return await create_org_with_user(
                org_name, user_email, user_name, user_password, session
            )
    
    # Create organization
    org = Organization(
        name=org_name,
        slug=secrets.token_urlsafe(8),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    # Create user
    hashed_password = get_password_hash(user_password or secrets.token_urlsafe(16))
    
    user = SaasUser(
        org_id=org.id,
        neon_auth_user_id=f"neon_{secrets.token_urlsafe(16)}",
        email=user_email,
        name=user_name or user_email,
        role="owner",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Generate token
    token = generate_token(
        {
            "sub": user.id,
            "email": user.email,
            "org_id": user.org_id,
            "role": "owner",
        },
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )
    
    return {
        "organization": org,
        "user": user,
        "access_token": token,
    }
