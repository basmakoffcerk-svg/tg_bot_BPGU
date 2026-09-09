import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.broadcaster import broadcaster_service

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint for monitoring."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e!s}"

    bot_status = "active" if broadcaster_service.bot else "uninitialized"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "telegram_bot": bot_status,
        "server_time": datetime.datetime.now().isoformat(),
    }
