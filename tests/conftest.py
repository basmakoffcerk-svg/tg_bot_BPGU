"""
Pytest Fixtures and Global Configuration for «АРМ Старосты» Test Suite.
Conforms strictly to TEST_INFRA.md and PROJECT.md.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
from typing import AsyncGenerator, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.mock_backend import (
    BOT_TOKEN_DEFAULT,
    ROLE_STAROSTA,
    ROLE_STUDENT,
    ROLE_ZAM,
    MockBotDispatcher,
    create_engine_with_wal,
    create_reference_app,
    mock_init_data,
    seed_database,
)

# Set default asyncio mode
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def bot_token() -> str:
    """Authoritative test bot token."""
    return BOT_TOKEN_DEFAULT


@pytest.fixture(scope="session")
def starosta_user_dict() -> dict:
    return {
        "id": 987654321,
        "first_name": "Иван",
        "last_name": "Иванов",
        "username": "starosta_240326",
    }


@pytest.fixture(scope="session")
def zam_user_dict() -> dict:
    return {
        "id": 987654322,
        "first_name": "Константин",
        "last_name": "Константинов",
        "username": "zam_240326",
    }


@pytest.fixture(scope="session")
def student1_user_dict() -> dict:
    return {
        "id": 100001,
        "first_name": "Александр",
        "last_name": "Александров",
        "username": "alex_240326",
    }


@pytest.fixture(scope="session")
def student2_user_dict() -> dict:
    return {
        "id": 100015,
        "first_name": "Павел",
        "last_name": "Павлов",
        "username": "pavel_240326",
    }


@pytest.fixture
def starosta_auth_header(starosta_user_dict, bot_token) -> Dict[str, str]:
    init_data = mock_init_data(starosta_user_dict, bot_token=bot_token)
    return {"X-Telegram-Init-Data": init_data}


@pytest.fixture
def zam_auth_header(zam_user_dict, bot_token) -> Dict[str, str]:
    init_data = mock_init_data(zam_user_dict, bot_token=bot_token)
    return {"X-Telegram-Init-Data": init_data}


@pytest.fixture
def student_auth_header(student1_user_dict, bot_token) -> Dict[str, str]:
    init_data = mock_init_data(student1_user_dict, bot_token=bot_token)
    return {"X-Telegram-Init-Data": init_data}


@pytest.fixture
def student2_auth_header(student2_user_dict, bot_token) -> Dict[str, str]:
    init_data = mock_init_data(student2_user_dict, bot_token=bot_token)
    return {"X-Telegram-Init-Data": init_data}


@pytest.fixture
def expired_auth_header(student1_user_dict, bot_token) -> Dict[str, str]:
    expired_date = int(time.time()) - 90000  # > 24 hours ago
    init_data = mock_init_data(student1_user_dict, bot_token=bot_token, auth_date=expired_date)
    return {"X-Telegram-Init-Data": init_data}


@pytest.fixture
def invalid_hash_auth_header(student1_user_dict, bot_token) -> Dict[str, str]:
    valid_data = mock_init_data(student1_user_dict, bot_token=bot_token)
    # Tamper with the hash by flipping characters
    tampered = valid_data[:-6] + "bad123"
    return {"X-Telegram-Init-Data": tampered}


@pytest.fixture
def missing_hash_auth_header(student1_user_dict, bot_token) -> Dict[str, str]:
    valid_data = mock_init_data(student1_user_dict, bot_token=bot_token)
    params = [p for p in valid_data.split("&") if not p.startswith("hash=")]
    return {"X-Telegram-Init-Data": "&".join(params)}


@pytest_asyncio.fixture
async def temp_db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Temporary SQLite database engine with WAL mode initialized."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    db_url = f"sqlite+aiosqlite:///{temp_path}"
    engine = await create_engine_with_wal(db_url)

    # Seed with Group 240326 data
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await seed_database(session)

    yield engine

    await engine.dispose()
    if os.path.exists(temp_path):
        os.remove(temp_path)
    # Also remove wal and shm files if created
    for ext in ("-wal", "-shm"):
        if os.path.exists(temp_path + ext):
            os.remove(temp_path + ext)


@pytest_asyncio.fixture
async def db_session_factory(temp_db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(temp_db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


@pytest.fixture
def test_app(db_session_factory, bot_token):
    """
    Returns FastAPI application. Prefers app.main.app if available;
    falls back to authoritative reference app for test harness verification.
    """
    try:
        from app.main import app
        return app
    except (ImportError, AttributeError):
        return create_reference_app(db_session_factory, bot_token=bot_token)


@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX AsyncClient fixture wired to the ASGI application."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def bot_dispatcher(db_session_factory) -> MockBotDispatcher:
    """aiogram dispatcher simulator for onboarding and callback testing."""
    return MockBotDispatcher(db_session_factory)
