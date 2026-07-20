"""
Plan router for Saas-api.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from ..schemas import (
    PlanCreate,
    PlanResponse,
    PlanListResponse,
)
from ..database import get_db
from ..auth import get_current_user
from saas_db.models import Plan, SaasUser


router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    plan_data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Create a new plan.
    
    Only owners and admins can create plans.
    """
    # Check permissions
    if current_user.role.value not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can create plans",
        )
    
    # Check if plan with this name exists
    result = await db.execute(
        select(Plan).where(Plan.name == plan_data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan with this name already exists",
        )
    
    # Create plan
    plan = Plan(
        name=plan_data.name,
        description=plan_data.description,
        price=plan_data.price,
        interval=plan_data.interval,
        trial_period_days=plan_data.trial_period_days,
        max_agent_tasks_per_month=plan_data.max_agent_tasks_per_month,
        max_api_calls_per_month=plan_data.max_api_calls_per_month,
        max_storage_gb=plan_data.max_storage_gb,
        max_voice_minutes_per_month=plan_data.max_voice_minutes_per_month,
        max_shipments_tracked=plan_data.max_shipments_tracked,
        max_routes_optimized=plan_data.max_routes_optimized,
        max_inventory_items=plan_data.max_inventory_items,
        features=plan_data.features,
        stripe_price_id=plan_data.stripe_price_id,
        sort_order=plan_data.sort_order,
        is_active=plan_data.is_active,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    
    return PlanResponse.from_orm(plan)


@router.get("/", response_model=PlanListResponse)
async def list_plans(
    is_active: bool = True,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    List plans.
    
    Anyone can list active plans.
    """
    query = select(Plan)
    
    if is_active:
        query = query.where(Plan.is_active == True)
    
    # Count total
    count_result = await db.execute(
        select([func.count()]).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Get plans
    query = query.order_by(Plan.sort_order).limit(limit).offset(offset)
    result = await db.execute(query)
    plans = result.scalars().all()
    
    return PlanListResponse(
        plans=[PlanResponse.from_orm(plan) for plan in plans],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a plan by ID.
    """
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    
    return PlanResponse.from_orm(plan)


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: str,
    plan_data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Update a plan.
    
    Only owners and admins can update plans.
    """
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    
    # Check permissions
    if current_user.role.value not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update plans",
        )
    
    # Update plan
    if plan_data.name:
        plan.name = plan_data.name
    if plan_data.description:
        plan.description = plan_data.description
    if plan_data.price:
        plan.price = plan_data.price
    if plan_data.interval:
        plan.interval = plan_data.interval
    if plan_data.trial_period_days:
        plan.trial_period_days = plan_data.trial_period_days
    if plan_data.max_agent_tasks_per_month:
        plan.max_agent_tasks_per_month = plan_data.max_agent_tasks_per_month
    if plan_data.max_api_calls_per_month:
        plan.max_api_calls_per_month = plan_data.max_api_calls_per_month
    if plan_data.max_storage_gb:
        plan.max_storage_gb = plan_data.max_storage_gb
    if plan_data.max_voice_minutes_per_month:
        plan.max_voice_minutes_per_month = plan_data.max_voice_minutes_per_month
    if plan_data.max_shipments_tracked:
        plan.max_shipments_tracked = plan_data.max_shipments_tracked
    if plan_data.max_routes_optimized:
        plan.max_routes_optimized = plan_data.max_routes_optimized
    if plan_data.max_inventory_items:
        plan.max_inventory_items = plan_data.max_inventory_items
    if plan_data.features:
        plan.features = plan_data.features
    if plan_data.stripe_price_id:
        plan.stripe_price_id = plan_data.stripe_price_id
    if plan_data.sort_order:
        plan.sort_order = plan_data.sort_order
    if plan_data.is_active:
        plan.is_active = plan_data.is_active
    
    await db.commit()
    await db.refresh(plan)
    
    return PlanResponse.from_orm(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: SaasUser = Depends(get_current_user),
):
    """
    Delete a plan.
    
    Only owners can delete plans.
    """
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    
    # Check permissions
    if current_user.role.value != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can delete plans",
        )
    
    # Delete plan
    await db.delete(plan)
    await db.commit()
