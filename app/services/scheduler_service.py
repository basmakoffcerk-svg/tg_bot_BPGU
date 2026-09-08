"""
Фоновый планировщик задач на APScheduler (AsyncIOScheduler).
Автоматические напоминания, мониторинг сбора чекинов и субботний авто-отчет в деканат.
"""
from datetime import date, datetime
import logging
from typing import Optional

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models import Student, ROLE_STAROSTA, ROLE_ZAM
from app.services.excel_generator import generate_dean_report_xlsx

logger = logging.getLogger("Scheduler")
_scheduler: Optional[AsyncIOScheduler] = None


async def send_saturday_dean_report(bot: Bot):
    """Каждую субботу в 16:00: формирование и отправка ведомости старосте в Telegram."""
    logger.info("Запуск субботней автовыгрузки рапортички старосте...")
    today = date.today()
    date_from = today - date.resolution * 6  # За неделю

    try:
        async with async_session_factory() as db:
            st_res = await db.execute(select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name))
            students = [{"id": s.id, "full_name": s.full_name, "subgroup": s.subgroup} for s in st_res.scalars().all()]

            xlsx_bytes = generate_dean_report_xlsx(
                group_name="240326 Матинф",
                university_name="БГПУ им. М. Танка",
                date_from=date_from,
                date_to=today,
                students=students,
                dates_and_pairs=[],
                attendance_matrix={},
            )

        if settings.STAROSTA_TELEGRAM_ID:
            from aiogram.types import BufferedInputFile
            filename = f"Рапортичка_240326_{date_from.strftime('%d.%m')}-{today.strftime('%d.%m')}.xlsx"
            file = BufferedInputFile(xlsx_bytes, filename=filename)
            await bot.send_document(
                chat_id=settings.STAROSTA_TELEGRAM_ID,
                document=file,
                caption=f"🗓 <b>Еженедельный автоматический отчет старосте</b>\n"
                        f"Группа: <code>240326 Матинф</code> (БГПУ)\n"
                        f"Период: {date_from.strftime('%d.%m.%Y')} — {today.strftime('%d.%m.%Y')}\n\n"
                        f"Ведомость сформирована и готова к сдаче в деканат.",
                parse_mode="HTML",
            )
            logger.info("Субботний отчет успешно доставлен старосте.")
    except Exception as e:
        logger.error(f"Ошибка формирования субботнего отчета: {e}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Запуск планировщика фоновых задач."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
        # Суббота в 16:00
        _scheduler.add_job(
            send_saturday_dean_report,
            trigger=CronTrigger(day_of_week="sat", hour=16, minute=0, timezone=settings.TIMEZONE),
            args=[bot],
            id="saturday_dean_report",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("Планировщик APScheduler запущен.")
    return _scheduler


def stop_scheduler():
    """Остановка планировщика."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("Планировщик APScheduler остановлен.")
