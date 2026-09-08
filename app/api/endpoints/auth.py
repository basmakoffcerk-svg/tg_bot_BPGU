"""
Telegram Mini App authentication and profile bootstrap.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import ProblemException, ProblemType
from app.core.time_utils import get_current_week_info
from app.database.models import Student, StudentStatus
from app.schemas.auth import (
    CurrentWeekInfo,
    PermissionsInfo,
    TelegramAuthResponse,
    UserProfile,
)

router = APIRouter()


@router.post("/telegram", response_model=TelegramAuthResponse, summary="Validate initData and get profile")
async def auth_telegram(
    current_user: Student = Depends(get_current_user),
) -> TelegramAuthResponse:
    """
    Validates Telegram initData, resolves the student's profile, permissions matrix,
    and current academic week calculation.
    """
    status_val = current_user.status.value if hasattr(current_user.status, "value") else str(current_user.status)
    if status_val == StudentStatus.PENDING.value or status_val == "PENDING":
        raise ProblemException(
            status_code=403,
            title="Аккаунт ожидает подтверждения",
            detail="Ваша учетная запись ожидает подтверждения старостой.",
            type_=ProblemType.ACCOUNT_PENDING,
        )

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    is_starosta = (role_val == "STAROSTA")
    is_admin = role_val in ("STAROSTA", "ZAM")

    permissions = PermissionsInfo(
        can_view_grid=is_admin,
        can_override_status=is_admin,
        can_lock_pairs=is_starosta,
        can_broadcast_critical=is_starosta,
        can_export_reports=is_admin,
    )

    now_local = datetime.now(ZoneInfo(settings.TIMEZONE))
    week_info = get_current_week_info(now_local.date())

    current_week = CurrentWeekInfo(
        week_number=week_info.week_number,
        week_type=week_info.week_type.value,
        is_study_day=week_info.is_study_day,
    )

    user_profile = UserProfile(
        id=current_user.id,
        telegram_id=current_user.telegram_id,
        full_name=current_user.full_name,
        subgroup=current_user.subgroup,
        role=role_val,
        status=status_val,
    )

    return TelegramAuthResponse(
        user=user_profile,
        permissions=permissions,
        current_week=current_week,
    )
