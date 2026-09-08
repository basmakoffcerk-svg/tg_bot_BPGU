"""
Public healthcheck and service telemetry.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.schemas.health import HealthCheckResponse

router = APIRouter()


@router.get("", response_model=HealthCheckResponse, summary="Public healthcheck")
async def get_health(db: AsyncSession = Depends(get_db)) -> HealthCheckResponse:
    """Verifies SQLite WAL database availability and server responsiveness."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    bot_status = "online" if settings.BOT_TOKEN else "unconfigured"

    return HealthCheckResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        bot=bot_status,
    )
