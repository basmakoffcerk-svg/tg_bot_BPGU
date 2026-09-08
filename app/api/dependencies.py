"""
Зависимости и авторизационные фильтры FastAPI (RBAC + HMAC-SHA256).
"""
import json
from typing import List, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import validate_telegram_init_data
from app.models import Student, ROLE_STUDENT, ROLE_ZAM, ROLE_STAROSTA


async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: AsyncSession = Depends(get_db_session),
) -> Student:
    """Извлекает и валидирует Telegram пользователя из initData."""
    validated = validate_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)
    if not validated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная или просроченная криптографическая подпись initData.",
        )

    user_json = validated.get("user")
    if not user_json:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="В initData отсутствуют данные пользователя.",
        )

    try:
        user_dict = json.loads(user_json)
        tg_id = int(user_dict["id"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный формат поля user в initData.",
        )

    # Поиск студента в БД
    stmt = select(Student).where(Student.telegram_id == tg_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()

    if not student and tg_id == settings.STAROSTA_TELEGRAM_ID:
        first_name = user_dict.get("first_name", "")
        last_name = user_dict.get("last_name", "")
        full_name = f"{last_name} {first_name}".strip() or "Староста"
        student = Student(
            full_name=full_name,
            subgroup=1,
            role=ROLE_STAROSTA,
            status="ACTIVE",
            telegram_id=tg_id,
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не зарегистрирован в базе группы. Обратитесь к старосте.",
        )

    if student.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Учетная запись находится в статусе {student.status}.",
        )

    return student


def require_roles(allowed_roles: List[str]):
    """Фабрика зависимостей для проверки ролей пользователя."""
    async def role_checker(current_user: Student = Depends(get_current_user)) -> Student:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав. Требуется роль: {', '.join(allowed_roles)}.",
            )
        return current_user
    return role_checker
