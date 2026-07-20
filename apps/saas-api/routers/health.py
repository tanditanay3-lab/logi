"""
Health router for Saas-api.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..auth import get_current_user
from saas_db.models import SaasUser


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "saas-api",
        "version": "0.1.0",
    }


@router.get("/db")
async def db_health_check(
    db: AsyncSession = Depends(get_db),
):
    """Database health check."""
    # Try a simple query
    try:
        result = await db.execute("SELECT 1")
        result.scalar()
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": str(e),
        }


@router.get("/auth")
async def auth_health_check(
    current_user: SaasUser = Depends(get_current_user),
):
    """Authentication health check."""
    return {
        "status": "healthy",
        "authenticated": True,
        "user_id": current_user.id,
        "org_id": current_user.org_id,
    }
