"""
FastAPI dependency injection: Async database session management and Telegram RBAC guards.
"""

from __future__ import annotations

from typing import AsyncGenerator, Callable
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    InitDataPayload,
    TelegramUser,
    get_current_active_student,
    get_current_telegram_user,
    get_current_user,
    get_validated_init_data,
    require_roles,
    require_starosta,
    require_zam_or_starosta,
)
from app.database.connection import get_session
from app.database.models import Student


# Direct alias so FastAPI's dependency injection reuses the single session per request
get_db = get_session


__all__ = [
    "get_db",
    "get_validated_init_data",
    "get_current_telegram_user",
    "get_current_user",
    "get_current_active_student",
    "require_roles",
    "require_zam_or_starosta",
    "require_starosta",
    "InitDataPayload",
    "TelegramUser",
    "Student",
]
