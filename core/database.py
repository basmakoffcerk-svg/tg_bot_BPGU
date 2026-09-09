import os
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

# Ensure data directory exists
db_url = settings.DATABASE_URL
if "sqlite" in db_url:
    path_part = db_url.split("///")[-1]
    if path_part and "/" in path_part:
        dir_name = os.path.dirname(path_part)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

# Automatic driver adjustment for PostgreSQL/SQLite
raw_db_url = settings.DATABASE_URL
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif raw_db_url.startswith("postgresql://") and "+asyncpg" not in raw_db_url:
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Performance-tuned async engine
engine = create_async_engine(
    raw_db_url,
    echo=(settings.APP_ENV == "debug"),
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in raw_db_url else {},
)


# Apply PRAGMAs on every connection
if "sqlite" in settings.DATABASE_URL:

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA cache_size = -64000;")  # 64MB cache
        cursor.execute("PRAGMA temp_store = MEMORY;")
        cursor.execute("PRAGMA mmap_size = 268435456;")  # 256MB memory-mapped IO
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
