"""
Organization router for Saas-api.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from .. import models
from ..schemas import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationListResponse,
)
from ..database import get_db
from ..auth import get_current_user, get_current_org
from saas_db.models import Organization, SaasUser


router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Create a new organization.
    
    Only owners and admins can create organizations.
    """
    # Check permissions
    if current_user.role.value not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can create organizations",
        )
    
    # Generate slug if not provided
    slug = org_data.slug or org_data.name.lower().replace(" ", "-")
    
    # Check if slug exists
    result = await db.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this slug already exists",
        )
    
    # Create organization
    org = Organization(
        name=org_data.name,
        slug=slug,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    return OrganizationResponse.from_orm(org)


@router.get("/", response_model=OrganizationListResponse)
async def list_organizations(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    List organizations.
    
    Owners see all organizations, others see only their own.
    """
    query = select(Organization)
    
    if current_user.role.value not in ["owner", "admin"]:
        # Only show user's organization
        query = query.where(Organization.id == current_user.org_id)
    
    # Count total
    count_result = await db.execute(
        select([func.count()]).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Get organizations
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    organizations = result.scalars().all()
    
    return OrganizationListResponse(
        organizations=[OrganizationResponse.from_orm(org) for org in organizations],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Get an organization by ID.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    # Check permissions
    if current_user.role.value not in ["owner", "admin"] and current_user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return OrganizationResponse.from_orm(org)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    org_data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Update an organization.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    # Check permissions
    if current_user.role.value not in ["owner", "admin"] and current_user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Update organization
    if org_data.name:
        org.name = org_data.name
    if org_data.slug:
        org.slug = org_data.slug
    
    await db.commit()
    await db.refresh(org)
    
    return OrganizationResponse.from_orm(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Delete an organization.
    
    Only owners can delete organizations.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    # Check permissions
    if current_user.role.value != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can delete organizations",
        )
    
    # Delete organization
    await db.delete(org)
    await db.commit()


# Import func for count
from sqlalchemy import func
