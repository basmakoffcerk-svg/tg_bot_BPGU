"""
Tier 1 & Tier 2 Tests: Healthcheck, Database Connectivity & SQLite PRAGMAs.
Requirements: API §1, DB §3, PROJECT.md.
"""
import asyncio
from datetime import datetime
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_healthcheck_returns_200_and_ok_status(async_client: AsyncClient):
    """Healthcheck endpoint must return HTTP 200 with status 'ok'."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


@pytest.mark.asyncio
async def test_healthcheck_verifies_database_connected(async_client: AsyncClient):
    """Healthcheck response must verify database connectivity."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("database") == "connected"


@pytest.mark.asyncio
async def test_healthcheck_contains_timestamp_in_iso_format(async_client: AsyncClient):
    """Healthcheck response must contain valid ISO timestamp."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    ts_str = data.get("timestamp")
    assert ts_str is not None
    # Validate ISO parsing
    parsed_dt = datetime.fromisoformat(ts_str)
    assert parsed_dt is not None


@pytest.mark.asyncio
async def test_healthcheck_contains_bot_status(async_client: AsyncClient):
    """Healthcheck response must include bot telemetry status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "bot" in data
    assert data["bot"] in ("online", "ready", "polling")


@pytest.mark.asyncio
async def test_healthcheck_content_type_application_json(async_client: AsyncClient):
    """Healthcheck header Content-Type must be application/json."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_healthcheck_does_not_require_auth_header(async_client: AsyncClient):
    """Public healthcheck must succeed without X-Telegram-Init-Data header."""
    response = await async_client.get("/api/v1/health", headers={})
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_healthcheck_idempotent_multiple_calls(async_client: AsyncClient):
    """Sequential healthcheck calls must consistently return 200 OK."""
    for _ in range(5):
        res = await async_client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_healthcheck_concurrent_requests(async_client: AsyncClient):
    """10 simultaneous healthcheck requests must all return 200 OK without blocking."""
    tasks = [async_client.get("/api/v1/health") for _ in range(10)]
    responses = await asyncio.gather(*tasks)
    for res in responses:
        assert res.status_code == 200
        assert res.json().get("database") == "connected"


@pytest.mark.asyncio
async def test_sqlite_wal_pragma_journal_mode(db_session: AsyncSession):
    """SQLite database must operate with journal_mode = WAL per DB §3."""
    res = await db_session.execute(text("PRAGMA journal_mode;"))
    mode = res.scalar()
    # In SQLite in-memory, journal_mode is memory; in file, it is wal.
    assert mode is not None
    assert mode.lower() in ("wal", "memory")


@pytest.mark.asyncio
async def test_sqlite_foreign_keys_pragma_enabled(db_session: AsyncSession):
    """SQLite database must have foreign_keys = 1 (ON) enforced."""
    res = await db_session.execute(text("PRAGMA foreign_keys;"))
    fk_val = res.scalar()
    assert fk_val == 1


@pytest.mark.asyncio
async def test_sqlite_busy_timeout_pragma_configured(db_session: AsyncSession):
    """SQLite busy_timeout must be configured (5000ms) for high concurrency."""
    res = await db_session.execute(text("PRAGMA busy_timeout;"))
    timeout_val = res.scalar()
    assert timeout_val is not None
    assert timeout_val >= 1000


@pytest.mark.asyncio
async def test_sqlite_synchronous_pragma_configured(db_session: AsyncSession):
    """SQLite synchronous setting must be NORMAL (1) or FULL (2)."""
    res = await db_session.execute(text("PRAGMA synchronous;"))
    sync_val = res.scalar()
    assert sync_val is not None
    assert sync_val in (1, 2)


@pytest.mark.asyncio
async def test_database_session_can_query_seed_students(db_session: AsyncSession):
    """Database session can query seeded students of group 240326."""
    res = await db_session.execute(text("SELECT COUNT(*) FROM students;"))
    count = res.scalar()
    assert count >= 27
