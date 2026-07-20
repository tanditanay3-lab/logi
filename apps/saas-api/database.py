"""
Database utilities for Saas-api.
"""

from typing import AsyncGenerator

from saas_db.database import (
    get_async_db_session,
    init_db as saas_db_init,
    close_db as saas_db_close,
)
from saas_db.models import Base


async def get_db():
    """Get database session."""
    async for session in get_async_db_session():
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database."""
    await saas_db_init()


async def close_db():
    """Close database connections."""
    await saas_db_close()
