"""
Инициализация бота и диспетчера aiogram 3.x с поддержкой FSM и модульных роутеров.
"""
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import (
    admin_router,
    broadcast_router,
    common_router,
    import_export_router,
    student_router,
)
from app.core.config import settings

_bot: Optional[Bot] = None
_dp: Optional[Dispatcher] = None


def get_bot() -> Bot:
    """Возвращает или инициализирует экземпляр бота."""
    global _bot
    if _bot is None:
        _bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


def get_dispatcher() -> Dispatcher:
    """Возвращает или инициализирует диспетчер с FSM хранилищем и роутерами."""
    global _dp
    if _dp is None:
        storage = MemoryStorage()
        _dp = Dispatcher(storage=storage)
        # Порядок подключения роутеров
        _dp.include_router(common_router)
        _dp.include_router(admin_router)
        _dp.include_router(import_export_router)
        _dp.include_router(broadcast_router)
        _dp.include_router(student_router)
    return _dp
