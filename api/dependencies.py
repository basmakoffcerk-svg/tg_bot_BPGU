import json
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.security import validate_telegram_init_data
from models import RoleEnum, Student, StudentStatusEnum


async def get_current_user(
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"), db: AsyncSession = Depends(get_db)
) -> Student:
    """
    Validates X-Telegram-Init-Data header and fetches authenticated Student from database.
    """
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "title": "Отсутствует заголовок авторизации",
                "detail": "Запрос должен содержать заголовок X-Telegram-Init-Data.",
            },
        )

    # Validate HMAC signature
    parsed_data = validate_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)
    if not parsed_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "title": "Недействительная подпись initData",
                "detail": "Подпись данных Telegram не прошла криптографическую проверку HMAC-SHA256.",
            },
        )

    # Extract telegram_id from 'user' field
    user_raw = parsed_data.get("user")
    tg_user_id = None
    if isinstance(user_raw, str):
        try:
            tg_user = json.loads(user_raw)
            tg_user_id = tg_user.get("id")
        except Exception:
            pass
    elif isinstance(user_raw, dict):
        tg_user_id = user_raw.get("id")

    if not tg_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "title": "Некорректный профиль пользователя",
                "detail": "Не удалось извлечь ID пользователя из данных Telegram.",
            },
        )

    # Find student in DB
    res = await db.execute(select(Student).where(Student.telegram_id == tg_user_id))
    student = res.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "title": "Студент не найден в вайтлисте группы",
                "detail": (
                    "Ваш Telegram ID не привязан к списку группы 240326. "
                    "Пройдите регистрацию в боте через /start."
                ),
            },
        )

    if student.status == StudentStatusEnum.BLOCKED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"title": "Доступ заблокирован", "detail": "Ваша учетная запись временно заблокирована старостой."},
        )

    return student


def require_roles(*allowed_roles: RoleEnum) -> Callable:
    """Dependency factory checking if current user has one of the allowed roles."""
    role_values = [r.value if isinstance(r, RoleEnum) else str(r) for r in allowed_roles]

    async def role_checker(user: Student = Depends(get_current_user)) -> Student:
        if user.role not in role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "title": "Недостаточно прав доступа",
                    "detail": f"Для выполнения данного действия требуются права: {', '.join(role_values)}.",
                },
            )
        return user

    return role_checker
