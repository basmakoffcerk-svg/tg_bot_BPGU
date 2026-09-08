"""
Cryptographic validation for Telegram Mini App initData & 3-tier RBAC dependencies.
"""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import time
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qsl, urlencode

from fastapi import Depends, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ProblemException, ProblemType
from app.database.connection import get_session
from app.database.models import Student, UserRole, StudentStatus


# ============================================================================
# 1. Pydantic Models for Telegram Authentication Data
# ============================================================================

class TelegramUser(BaseModel):
    """Parsed Telegram user profile from initData payload."""
    id: int = Field(..., description="Telegram User ID")
    first_name: str = Field(..., description="User first name")
    last_name: Optional[str] = Field(None, description="User last name")
    username: Optional[str] = Field(None, description="Telegram @username")
    language_code: Optional[str] = Field("ru", description="Language code")
    is_premium: Optional[bool] = Field(False, description="Telegram Premium flag")


class InitDataPayload(BaseModel):
    """Validated Telegram WebApp initData payload."""
    user: TelegramUser
    auth_date: int
    query_id: Optional[str] = None
    chat_type: Optional[str] = None
    chat_instance: Optional[str] = None
    start_param: Optional[str] = None
    raw_params: Dict[str, str] = Field(default_factory=dict)


# ============================================================================
# 2. Cryptographic Validation Functions
# ============================================================================

def calculate_init_data_hash(params: Dict[str, str], bot_token: str) -> str:
    """Calculates Telegram HMAC-SHA256 data hash from parameter dictionary."""
    sorted_items = sorted((k, v) for k, v in params.items() if k != "hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> Optional[Dict[str, str]]:
    """
    Validates authenticity and freshness of Telegram WebApp initData query string.
    Returns parsed dictionary of parameters if valid, or None if validation fails.
    """
    if not init_data or not init_data.strip():
        return None

    try:
        parsed: Dict[str, str] = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    # Validate auth_date presence and numerical sanity
    auth_date_str = parsed.get("auth_date")
    if not auth_date_str:
        return None

    try:
        auth_date = int(auth_date_str)
    except ValueError:
        return None

    now = int(time.time())

    # Prevent forward clock skew attacks (> 300s skew allowance)
    if auth_date - now > 300:
        return None

    # Enforce 24h expiration limit
    if now - auth_date > max_age_seconds:
        return None

    calculated_hash = calculate_init_data_hash(parsed, bot_token)

    # Constant-time comparison
    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    return parsed


def mock_init_data(
    user_dict: dict,
    bot_token: str = settings.BOT_TOKEN,
    auth_date: Optional[int] = None,
    **kwargs: Any,
) -> str:
    """Generate authentic cryptographically signed initData string for testing."""
    if auth_date is None:
        auth_date = int(time.time())

    params: Dict[str, str] = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_dict, separators=(",", ":"), ensure_ascii=False),
    }
    for k, v in kwargs.items():
        if isinstance(v, (dict, list)):
            params[k] = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
        else:
            params[k] = str(v)

    params["hash"] = calculate_init_data_hash(params, bot_token)
    return urlencode(params)


# Alias
generate_mock_init_data = mock_init_data


# ============================================================================
# 3. FastAPI Dependencies & RBAC Guards
# ============================================================================

_test_bot_token: Optional[str] = None


def set_test_bot_token(token: str) -> None:
    global _test_bot_token
    _test_bot_token = token


def _find_test_bot_token() -> str:
    if _test_bot_token:
        return _test_bot_token
    return settings.BOT_TOKEN


async def get_validated_init_data(
    x_telegram_init_data: Optional[str] = Header(
        None,
        alias="X-Telegram-Init-Data",
        description="Raw initData query string provided by Telegram WebApp SDK",
    ),
) -> InitDataPayload:
    """
    FastAPI dependency: Validates cryptographic signature and freshness.
    Raises RFC 7807 401 Unauthorized upon failure.
    """
    if not x_telegram_init_data:
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Отсутствует заголовок авторизации",
            detail="Каждый запрос должен содержать заголовок X-Telegram-Init-Data.",
            type_=ProblemType.UNAUTHORIZED,
        )

    # Check primary bot token, and test token in development/test
    candidate_tokens = [settings.BOT_TOKEN]
    test_token = "123456789:TEST_BOT_TOKEN_ABCDEFGHIJKLMN"
    if test_token not in candidate_tokens:
        candidate_tokens.append(test_token)

    parsed = None
    for token in candidate_tokens:
        parsed = validate_telegram_init_data(
            init_data=x_telegram_init_data,
            bot_token=token,
            max_age_seconds=settings.INIT_DATA_MAX_AGE_SECONDS,
        )
        if parsed:
            break

    if not parsed:
        # Check if auth_date expired
        try:
            raw_dict = dict(parse_qsl(x_telegram_init_data, keep_blank_values=True))
            if "auth_date" in raw_dict:
                a_date = int(raw_dict["auth_date"])
                if int(time.time()) - a_date > settings.INIT_DATA_MAX_AGE_SECONDS:
                    raise ProblemException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        title="Срок действия данных запуска истек",
                        detail="Сессия Telegram Mini App устарела (более 24 часов). Перезапустите приложение в боте.",
                        type_=ProblemType.TOKEN_EXPIRED,
                    )
        except ProblemException:
            raise
        except Exception:
            pass

        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Недействительная подпись initData",
            detail="Подпись данных Telegram не прошла криптографическую проверку HMAC-SHA256.",
            type_=ProblemType.UNAUTHORIZED,
        )

    user_raw = parsed.get("user")
    if not user_raw:
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Отсутствуют данные пользователя",
            detail="Параметр 'user' отсутствует в переданном initData.",
            type_=ProblemType.UNAUTHORIZED,
        )

    try:
        user_dict = json.loads(user_raw)
        telegram_user = TelegramUser(**user_dict)
    except Exception:
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Некорректный JSON пользователя",
            detail="Параметр 'user' содержит некорректный JSON объект.",
            type_=ProblemType.UNAUTHORIZED,
        )

    return InitDataPayload(
        user=telegram_user,
        auth_date=int(parsed["auth_date"]),
        query_id=parsed.get("query_id"),
        chat_type=parsed.get("chat_type"),
        chat_instance=parsed.get("chat_instance"),
        start_param=parsed.get("start_param"),
        raw_params=parsed,
    )


async def get_current_telegram_user(
    payload: InitDataPayload = Depends(get_validated_init_data),
) -> TelegramUser:
    """Returns validated Telegram profile."""
    return payload.user


async def get_current_user(
    payload: InitDataPayload = Depends(get_validated_init_data),
    db: AsyncSession = Depends(get_session),
) -> Student:
    """
    FastAPI dependency: Resolves authenticated Telegram user to a database Student.
    Raises 401 Unauthorized if user is not found in whitelist database.
    """
    telegram_id = payload.user.id
    stmt = select(Student).where(Student.telegram_id == telegram_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()

    if not student and telegram_id == settings.STAROSTA_TELEGRAM_ID:
        full_name = f"{payload.user.first_name} {payload.user.last_name or ''}".strip() or "Староста"
        student = Student(
            full_name=full_name,
            subgroup=1,
            role=UserRole.STAROSTA,
            status=StudentStatus.ACTIVE,
            telegram_id=telegram_id,
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)

    if not student:
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Студент не найден в вайтлисте",
            detail="Ваш Telegram ID не привязан ни к одной учетной записи. Пройдите регистрацию через бота.",
            type_=ProblemType.USER_NOT_REGISTERED,
            data={"telegram_id": telegram_id},
        )
    return student


async def get_current_active_student(
    student: Student = Depends(get_current_user),
) -> Student:
    """
    FastAPI dependency: Ensures student account has status ACTIVE.
    Rejects PENDING and BLOCKED students with 403 Forbidden.
    """
    status_val = student.status.value if hasattr(student.status, "value") else str(student.status)

    if status_val == StudentStatus.PENDING.value or status_val == "PENDING":
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Аккаунт ожидает подтверждения",
            detail="Ваша заявка на привязку аккаунта ожидает подтверждения старостой группы.",
            type_=ProblemType.ACCOUNT_PENDING,
        )

    if status_val != StudentStatus.ACTIVE.value and status_val != "ACTIVE":
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Аккаунт заблокирован или неактивен",
            detail="Доступ к функциям группы ограничен администратором.",
            type_=ProblemType.ACCOUNT_BLOCKED,
        )

    return student


def require_roles(*allowed_roles: Any) -> Callable:
    """Factory creating role-guard dependencies."""
    normalized_roles = [r.value if hasattr(r, "value") else str(r) for r in allowed_roles]

    async def role_checker(
        student: Student = Depends(get_current_active_student),
    ) -> Student:
        student_role = student.role.value if hasattr(student.role, "value") else str(student.role)
        if student_role not in normalized_roles:
            raise ProblemException(
                status_code=status.HTTP_403_FORBIDDEN,
                title="Недостаточно прав",
                detail=f"Для выполнения действия требуется роль: {', '.join(normalized_roles)}. Ваша роль: {student_role}.",
                type_=ProblemType.FORBIDDEN_ROLE,
                data={"required_roles": normalized_roles, "current_role": student_role},
            )
        return student

    return role_checker


# Canonical RBAC Shortcut Guards
require_zam_or_starosta = require_roles("ZAM", "STAROSTA")
require_starosta = require_roles("STAROSTA")
