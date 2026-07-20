"""
Database utilities for Lanework SaaS layer.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .models import Base

# Get database URL from environment
DATABASE_URL = os.getenv(
    "SAAS_DATABASE_URL",
    "postgresql+asyncpg://neondb_owner:npg_3YDpWTUa2ifV@ep-bitter-block-az9ls0rp.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

# Sync engine for migrations
sync_engine = None

# Async engine for runtime
async_engine = None
AsyncSessionLocal = None


def get_sync_engine():
    """Get or create synchronous engine for migrations."""
    global sync_engine
    if sync_engine is None:
        # Convert asyncpg to psycopg2 for sync
        sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        from sqlalchemy import create_engine
        sync_engine = create_engine(sync_url, echo=False)
    return sync_engine


def get_async_engine():
    """Get or create asynchronous engine for runtime."""
    global async_engine
    if async_engine is None:
        async_engine = create_async_engine(DATABASE_URL, echo=False)
    return async_engine


def get_db_session():
    """Get a synchronous database session factory."""
    engine = get_sync_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def get_session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    return get_session


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an asynchronous database session."""
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        engine = get_async_engine()
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize the database - create all tables."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Apply RLS policies
    from .models import get_rls_setup_sql
    rls_sql = get_rls_setup_sql()
    
    async with engine.begin() as conn:
        await conn.execute(rls_sql)
    
    print("Database initialized with RLS policies")


async def drop_db():
    """Drop all tables - for testing only."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Database dropped")


async def get_db_state():
    """Get current database state."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        # Check if tables exist
        result = await conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = [row[0] for row in result]
        return {"tables": tables}


def set_current_org_id(org_id: str):
    """
    Set the current organization ID for RLS.
    
    This should be called at the start of each request to set the
    app.current_org_id setting that RLS policies use.
    """
    # In a real async context, this would be set via SQL
    # For now, we'll use a context variable
    import contextvars
    _current_org_id = contextvars.ContextVar('current_org_id', default=None)
    _current_org_id.set(org_id)


def get_current_org_id() -> str:
    """Get the current organization ID for RLS."""
    import contextvars
    _current_org_id = contextvars.ContextVar('current_org_id', default=None)
    return _current_org_id.get()


async def set_rls_context(org_id: str):
    """
    Set the RLS context for the current database session.
    
    This sets the app.current_org_id setting that RLS policies reference.
    """
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.execute(f"SELECT set_config('app.current_org_id', '{org_id}', false)")
