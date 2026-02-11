"""
Raw database connection and session management.
Read-only access to the task_manager database.
"""
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Raw DB engine and session (created lazily)
_raw_engine = None
_RawAsyncSessionLocal = None


def get_raw_engine():
    """Get or create the raw database engine (lazy initialization)."""
    global _raw_engine
    if _raw_engine is None and settings.RAW_DATABASE_URL:
        _raw_engine = create_async_engine(
            settings.RAW_DATABASE_URL,
            echo=settings.ENVIRONMENT == "development",
            pool_pre_ping=True,
            pool_size=5,  # Smaller pool for read-only access
            max_overflow=10,
        )
    return _raw_engine


def get_raw_session_factory():
    """Get or create the raw database session factory."""
    global _RawAsyncSessionLocal
    if _RawAsyncSessionLocal is None:
        engine = get_raw_engine()
        if engine is not None:
            _RawAsyncSessionLocal = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
    return _RawAsyncSessionLocal


def is_raw_db_configured() -> bool:
    """Check if raw database is configured."""
    return bool(settings.RAW_DATABASE_URL)


async def get_raw_db() -> AsyncGenerator[Optional[AsyncSession], None]:
    """Dependency to get raw database session (read-only).

    Returns None if raw database is not configured.
    """
    session_factory = get_raw_session_factory()
    if session_factory is None:
        yield None
        return

    async with session_factory() as session:
        try:
            yield session
            # No commit for read-only operations
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_raw_db_connection() -> bool:
    """Check if raw database connection is working."""
    if not is_raw_db_configured():
        return False

    try:
        session_factory = get_raw_session_factory()
        if session_factory is None:
            return False

        async with session_factory() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False
