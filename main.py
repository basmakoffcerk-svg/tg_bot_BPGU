import asyncio
import logging
import sys

import uvicorn

from api.app import create_app
from bot.bot import create_bot_and_dispatcher, setup_bot_commands
from core.config import settings
from core.database import engine
from data.seed_data import seed_database
from services.scheduler import setup_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


async def run_services():
    # 1. Ensure DB and seed data
    logger.info("[INIT] Checking and seeding database...")
    await seed_database()

    # 2. Initialize Bot and Dispatcher
    bot, dp = create_bot_and_dispatcher()
    await setup_bot_commands(bot)

    # 3. Setup Scheduler
    scheduler = setup_scheduler(bot)

    # 4. Create FastAPI app
    app = create_app()

    # 5. Start Uvicorn Server & Bot polling concurrently
    config = uvicorn.Config(app=app, host=settings.HOST, port=settings.PORT, log_level="info", lifespan="on")
    server = uvicorn.Server(config)

    logger.info(f"[STARTUP] Starting FastAPI server on http://{settings.HOST}:{settings.PORT}")
    logger.info("[STARTUP] Starting Telegram bot polling...")

    try:
        # Run Uvicorn and aiogram polling concurrently
        await asyncio.gather(server.serve(), dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()))
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("[SHUTDOWN] Stopping services...")
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()
        logger.info("[SHUTDOWN] Services stopped gracefully.")


def main():
    try:
        asyncio.run(run_services())
    except (KeyboardInterrupt, SystemExit):
        logger.info("[SHUTDOWN] Exiting...")


if __name__ == "__main__":
    main()
