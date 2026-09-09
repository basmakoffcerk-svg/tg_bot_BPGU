import datetime
import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.database import AsyncSessionLocal
from services.excel_generator import generate_attendance_excel

logger = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)


async def weekly_saturday_report_job(bot: Bot) -> None:
    """Scheduled task executed on Saturdays at 16:00 to send weekly attendance report."""
    logger.info("[SCHEDULER] Running weekly Saturday attendance report generation...")
    today = datetime.date.today()
    # Monday of the current week
    monday = today - datetime.timedelta(days=today.weekday())

    try:
        async with AsyncSessionLocal() as session:
            excel_buf, filename, total_pairs, total_absent_hours = await generate_attendance_excel(
                session=session, date_from=monday, date_to=today
            )

        caption = (
            f"📊 <b>Еженедельная рапортичка группы 240326</b>\n"
            f"Период: {monday.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}\n"
            f"Всего пар: {total_pairs}\n"
            f"Суммарно пропущено: {total_absent_hours} ч.\n\n"
            f"Файл сформирован автоматически планировщиком АРМ Старосты."
        )

        input_file = BufferedInputFile(excel_buf.getvalue(), filename=filename)

        if settings.STAROSTA_TELEGRAM_ID:
            await bot.send_document(
                chat_id=settings.STAROSTA_TELEGRAM_ID, document=input_file, caption=caption, parse_mode="HTML"
            )
            logger.info(f"[SCHEDULER] Weekly report sent to Starosta ({settings.STAROSTA_TELEGRAM_ID})")
    except Exception as e:
        logger.error(f"[SCHEDULER] Error in weekly report job: {e}", exc_info=True)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Sets up and starts APScheduler jobs."""
    # Every Saturday at 16:00
    scheduler.add_job(
        weekly_saturday_report_job,
        trigger="cron",
        day_of_week="sat",
        hour=16,
        minute=0,
        args=[bot],
        id="weekly_saturday_report",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
        logger.info("[SCHEDULER] APScheduler started.")
    return scheduler
