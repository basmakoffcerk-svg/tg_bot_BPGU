"""
Скрипт создания структуры базы данных.
Встроенные тестовые данные удалены: база чистая и готова к заполнению старостой.
"""
from sqlalchemy import select
from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.models import (
    Base,
    Student,
    ROLE_STAROSTA,
)


async def seed_database():
    """Создает таблицы и инициализирует профиль администратора (старосты)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Автоматически регистрируем старосту, если указан STAROSTA_TELEGRAM_ID
        if settings.STAROSTA_TELEGRAM_ID:
            res = await session.execute(
                select(Student).where(Student.telegram_id == settings.STAROSTA_TELEGRAM_ID)
            )
            starosta = res.scalar_one_or_none()
            if not starosta:
                starosta = Student(
                    full_name="Староста (Администратор)",
                    subgroup=1,
                    role=ROLE_STAROSTA,
                    status="ACTIVE",
                    telegram_id=settings.STAROSTA_TELEGRAM_ID,
                )
                session.add(starosta)
                await session.commit()
