"""
User router for Saas-api.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_

from ..schemas import (
    UserCreate,
    UserResponse,
    UserListResponse,
)
from ..database import get_db
from ..auth import get_current_user, get_current_org
from saas_db.models import SaasUser, Organization


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """
    Create a new user in the current organization.
    
    Only owners and admins can create users.
    """
    # Check permissions
    if current_user.role.value not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can create users",
        )
    
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
    
    # Create user
    from ..auth.neon_auth import get_password_hash
    hashed_password = get_password_hash(user_data.password)
    
    user = SaasUser(
        org_id=current_org.id,
        neon_auth_user_id=f"neon_{user_data.email}",
        email=user_data.email,
        name=user_data.name,
        role=user_data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.from_orm(user)


@router.get("/", response_model=UserListResponse)
async def list_users(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    List users in the current organization.
    """
    query = select(SaasUser).where(SaasUser.org_id == current_user.org_id)
    
    # Count total
    count_result = await db.execute(
        select([func.count()]).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Get users
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        users=[UserResponse.from_orm(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Get a user by ID.
    """
    result = await db.execute(
        select(SaasUser).where(SaasUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check permissions
    if current_user.role.value not in ["owner", "admin"] and current_user.org_id != user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return UserResponse.from_orm(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Update a user.
    """
    result = await db.execute(
        select(SaasUser).where(SaasUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check permissions
    if current_user.role.value not in ["owner", "admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Update user
    if user_data.email:
        user.email = user_data.email
    if user_data.name:
        user.name = user_data.name
    if user_data.role and current_user.role.value == "owner":
        user.role = user_data.role
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.from_orm(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Delete a user.
    
    Only owners can delete users.
    """
    result = await db.execute(
        select(SaasUser).where(SaasUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check permissions
    if current_user.role.value != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can delete users",
        )
    
    # Delete user
    await db.delete(user)
    await db.commit()
