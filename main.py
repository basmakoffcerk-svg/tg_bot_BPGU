"""
Главная точка входа АРМ Старосты («Пульт управления группой 240326»).
Запускает FastAPI сервер и фоновый опрос Telegram-бота (aiogram 3.x).
"""
import asyncio
from contextlib import asynccontextmanager
import logging
import uvicorn
from fastapi import FastAPI

from app.api.app import app
from app.bot.bot import get_bot, get_dispatcher
from app.core.config import settings
from app.core.seed import seed_database
from app.services.scheduler_service import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ARM_Starosta")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Жизненный цикл FastAPI приложения (Lifespan)."""
    logger.info("Инициализация базы данных и сидинг вайтлиста 240326...")
    await seed_database()
    logger.info("База данных готова к работе.")

    polling_task = None
    if not settings.WEBHOOK_URL:
        async def safe_polling():
            try:
                bot = get_bot()
                await bot.delete_webhook(drop_pending_updates=True)
                dp = get_dispatcher()
                logger.info("Запуск Telegram-бота в режиме Long Polling...")
                await dp.start_polling(bot, handle_signals=False)
            except Exception as e:
                logger.warning(f"Ошибка при работе Telegram-бота: {e}")
        polling_task = asyncio.create_task(safe_polling())

    else:
        try:
            bot = get_bot()
            logger.info(f"Настройка вебхука: {settings.WEBHOOK_URL}")
            await bot.set_webhook(url=settings.WEBHOOK_URL, secret_token=settings.WEBHOOK_SECRET)
        except Exception as e:
            logger.warning(f"Ошибка настройки вебхука: {e}")

    bot = get_bot()
    start_scheduler(bot)

    yield

    logger.info("Остановка приложения...")
    stop_scheduler()
    if polling_task:
        polling_task.cancel()
    try:
        await bot.session.close()
    except Exception:
        pass


app.router.lifespan_context = lifespan


def main():
    """Запуск Uvicorn сервера."""
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
