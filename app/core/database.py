from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings


def create_engine_with_wal(db_url: str = settings.DATABASE_URL) -> AsyncEngine:
    """Создает асинхронный движок для SQLite или PostgreSQL."""
    # Нормализация для Vercel Postgres / Neon (postgres:// -> postgresql+asyncpg://)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    is_sqlite = db_url.startswith("sqlite")
    if is_sqlite and ":///" in db_url:
        db_file_part = db_url.split(":///", 1)[1]
        if not db_file_part.startswith(":memory:"):
            try:
                Path(db_file_part).parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass

    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
    )

    if is_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


engine = create_engine_with_wal()
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

_db_initialized = False


async def ensure_db_initialized():
    """Гарантирует создание всех таблиц и профиля старосты."""
    global _db_initialized
    if not _db_initialized:
        try:
            from app.models import Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            _db_initialized = True
        except Exception as e:
            print(f"Warning initializing database tables: {e}")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для FastAPI для предоставления асинхронной сессии БД."""
    await ensure_db_initialized()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

