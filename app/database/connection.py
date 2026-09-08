"""
Database connection, AsyncEngine configuration, and session lifecycle.
Enforces SQLite WAL mode and foreign key constraints via event listeners.
"""

from collections.abc import AsyncGenerator
import inspect
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.database.models import Base

# Ensure data directory exists if SQLite file path is used
if "sqlite" in settings.DATABASE_URL and ":///" in settings.DATABASE_URL:
    db_file_part = settings.DATABASE_URL.split(":///", 1)[1]
    if not db_file_part.startswith(":memory:"):
        db_path = Path(db_file_part)
        if db_path.parent:
            db_path.parent.mkdir(parents=True, exist_ok=True)


def configure_sqlite_pragmas(engine: AsyncEngine) -> None:
    """
    Attach connection event listener to set SQLite pragmas on each connection.
    Uses engine.sync_engine for aiosqlite / SQLite DBAPI integration.
    """
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA cache_size = -64000;")
        cursor.close()


# Engine initialization
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    future=True,
)

# Apply WAL and FK pragmas
configure_sqlite_pragmas(engine)

# Async session factory
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Compatibility alias
async_session_maker = AsyncSessionLocal


_test_session_factory: Optional[Any] = None


def set_test_session_factory(factory: Any) -> None:
    """Explicitly set test session factory for testing integration."""
    global _test_session_factory
    _test_session_factory = factory


def get_test_session_factory() -> Optional[Any]:
    return _test_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for FastAPI and service layer.
    Ensures session commit/rollback and clean disposal.
    Supports transparent test fixture session injection.
    """
    factory = _test_session_factory or AsyncSessionLocal

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database schema (DDL) and verify foreign keys.
    Creates all tables declared in SQLAlchemy metadata.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Graceful disposal of connection pools upon application shutdown."""
    await engine.dispose()
