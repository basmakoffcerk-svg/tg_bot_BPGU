"""
Маршруты аутентификации и проверки сессии.
"""
from datetime import date
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.schemas import AuthResponseSchema, CurrentWeekSchema, UserProfileSchema
from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import generate_mock_init_data
from app.models import Student, ROLE_STAROSTA, ROLE_ZAM

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/telegram", response_model=AuthResponseSchema)
async def auth_telegram(current_user: Student = Depends(get_current_user)):
    """Валидирует сессию WebApp и возвращает профиль и права."""
    is_starosta = current_user.role == ROLE_STAROSTA
    is_admin = current_user.role in (ROLE_STAROSTA, ROLE_ZAM)

    today = date.today()
    week_number = today.isocalendar()[1]
    week_type = "ODD" if week_number % 2 != 0 else "EVEN"

    return AuthResponseSchema(
        user=UserProfileSchema(
            id=current_user.id,
            telegram_id=current_user.telegram_id,
            full_name=current_user.full_name,
            subgroup=current_user.subgroup,
            role=current_user.role,
            status=current_user.status,
        ),
        permissions={
            "can_view_grid": is_admin,
            "can_override_status": is_admin,
            "can_lock_pairs": is_starosta,
            "can_broadcast_critical": is_starosta,
            "can_export_reports": is_admin,
        },
        current_week=CurrentWeekSchema(
            week_number=week_number,
            week_type=week_type,
            is_study_day=today.weekday() < 6,
        ),
    )


@router.get("/dev-users")
async def get_dev_users(db: AsyncSession = Depends(get_db_session)):
    """Список тестовых пользователей для переключения в веб-интерфейсе при локальной отладке."""
    stmt = select(Student).where(Student.status == "ACTIVE").order_by(Student.id)
    res = await db.execute(stmt)
    students = res.scalars().all()
    return [
        {
            "id": s.id,
            "telegram_id": s.telegram_id,
            "full_name": s.full_name,
            "role": s.role,
            "subgroup": s.subgroup,
        }
        for s in students
    ]


@router.post("/dev-login")
async def dev_login(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Генерирует валидную криптографическую подпись initData для быстрого тестирования в обычном браузере."""
    stmt = select(Student).where(Student.telegram_id == telegram_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()

    name_parts = student.full_name.split() if student else ["Пользователь", "Тест"]
    user_dict = {
        "id": telegram_id,
        "first_name": name_parts[1] if len(name_parts) > 1 else name_parts[0],
        "last_name": name_parts[0] if len(name_parts) > 1 else "",
        "username": f"user_{telegram_id}",
    }
    signed_init_data = generate_mock_init_data(user_dict, settings.BOT_TOKEN)
    return {
        "telegram_id": telegram_id,
        "init_data": signed_init_data,
        "student_name": student.full_name if student else "Unknown",
    }
