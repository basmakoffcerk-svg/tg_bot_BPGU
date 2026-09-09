import datetime
import json

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.auth import (
    AuthResponse,
    CurrentWeekSchema,
    PermissionsSchema,
    UserProfileSchema,
)
from core.config import settings
from core.database import get_db
from core.security import validate_telegram_init_data
from models import RoleEnum, Student, WeekTypeEnum

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_current_week_info() -> CurrentWeekSchema:
    today = datetime.date.today()
    # Semester 1 (Autumn): Sep 1 - Jan 31
    # Semester 2 (Spring): Feb 1 - Jun 30
    if today.month >= 9:
        semester_start = datetime.date(today.year, 9, 1)
    elif today.month >= 2:
        semester_start = datetime.date(today.year, 2, 1)
    else:
        # January belongs to Autumn semester exam session
        semester_start = datetime.date(today.year - 1, 9, 1)

    delta_days = max(0, (today - semester_start).days)
    week_number = max(1, (delta_days // 7) + 1)
    week_type = WeekTypeEnum.ODD.value if (week_number % 2 != 0) else WeekTypeEnum.EVEN.value
    is_study_day = today.isoweekday() <= 6

    return CurrentWeekSchema(week_number=week_number, week_type=week_type, is_study_day=is_study_day)


@router.post("/telegram", response_model=AuthResponse)
async def authenticate_telegram(
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"), db: AsyncSession = Depends(get_db)
):
    """
    Authenticates Mini App user via Telegram initData HMAC-SHA256 signature.
    """
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "title": "Недействительная подпись initData",
                "detail": "Заголовок X-Telegram-Init-Data отсутствует.",
            },
        )

    parsed = validate_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "title": "Недействительная подпись initData",
                "detail": "Подпись данных Telegram не прошла криптографическую проверку HMAC-SHA256.",
            },
        )

    user_raw = parsed.get("user")
    tg_user_id = None
    if isinstance(user_raw, str):
        try:
            tg_user_id = json.loads(user_raw).get("id")
        except Exception:
            pass
    elif isinstance(user_raw, dict):
        tg_user_id = user_raw.get("id")

    student_profile = None
    permissions = PermissionsSchema(
        can_view_grid=False,
        can_override_status=False,
        can_lock_pairs=False,
        can_broadcast_critical=False,
        can_export_reports=False,
    )

    if tg_user_id:
        res = await db.execute(select(Student).where(Student.telegram_id == tg_user_id))
        student = res.scalar_one_or_none()
        if student:
            student_profile = UserProfileSchema(
                id=student.id,
                telegram_id=student.telegram_id,
                full_name=student.full_name,
                subgroup=student.subgroup,
                role=student.role,
                status=student.status,
            )
            is_starosta = student.role == RoleEnum.STAROSTA.value
            is_zam = student.role == RoleEnum.ZAM.value
            is_admin = is_starosta or is_zam

            permissions = PermissionsSchema(
                can_view_grid=is_admin,
                can_override_status=is_admin,
                can_lock_pairs=is_starosta,
                can_broadcast_critical=is_starosta,
                can_export_reports=is_admin,
            )

    return AuthResponse(user=student_profile, permissions=permissions, current_week=get_current_week_info())
