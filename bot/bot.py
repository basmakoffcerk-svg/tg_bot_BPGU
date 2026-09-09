import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from bot.handlers import commands_router, onboarding_router
from core.config import settings
from services.broadcaster import broadcaster_service

logger = logging.getLogger("bot")


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Register handlers
    dp.include_router(onboarding_router)
    dp.include_router(commands_router)
    from bot.handlers import chat_grid_router, schedule_upload_router
    dp.include_router(schedule_upload_router)
    dp.include_router(chat_grid_router)

    # Link bot instance to broadcaster service
    broadcaster_service.set_bot(bot)

    return bot, dp


async def setup_bot_commands(bot: Bot) -> None:
    """Configures default bot menu commands."""
    try:
        from aiogram.types import MenuButtonCommands
        commands = [
            BotCommand(command="start", description="Главное меню и статус"),
            BotCommand(command="status", description="Моя статистика посещаемости"),
            BotCommand(command="report", description="Выгрузка ведомости (староста)"),
            BotCommand(command="upload_schedule", description="Загрузка расписания Excel (староста)"),
            BotCommand(command="schedule_template", description="Шаблон расписания (.xlsx)"),
            BotCommand(command="help", description="Справка по системе"),
        ]
        await bot.set_my_commands(commands)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("[BOT] Bot commands configured, menu button set to commands.")
        logger.info("[BOT] Bot commands and menu button configured.")
    except Exception as e:
        logger.warning(f"[BOT] Could not setup bot commands: {e}")
