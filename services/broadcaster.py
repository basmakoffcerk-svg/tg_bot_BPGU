import asyncio
import html
import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models import BroadcastMessage, BroadcastTypeEnum, Student, StudentStatusEnum

logger = logging.getLogger("broadcaster")


class BroadcasterService:
    def __init__(self, bot: Bot | None = None):
        self.bot = bot
        self.rate_limit_delay = 0.04  # ~25 messages/second

    def set_bot(self, bot: Bot) -> None:
        self.bot = bot

    async def broadcast_alert(
        self, session: AsyncSession, sender_id: int, broadcast_type: str, title: str, body: str
    ) -> tuple[int, int]:
        """
        Sends broadcast message:
        - If CRITICAL: sends message to group chat and DMs to all active students.
        - If INFO: sends message to group chat.
        Returns: (broadcast_message_id, total_recipients)
        """
        # Save broadcast entry to DB
        bcast = BroadcastMessage(
            sender_id=sender_id, message_type=broadcast_type, title=title, body=body, total_recipients=0, read_count=0
        )
        session.add(bcast)
        await session.flush()

        if not self.bot:
            logger.warning("[BROADCASTER] Bot instance is not configured, skipping dispatch.")
            await session.commit()
            return bcast.id, 0

        # Sanitize HTML entities
        safe_title = html.escape(title)
        safe_body = html.escape(body)

        # 1. Post to Group Chat
        group_text = f"📢 <b>{safe_title}</b>\n\n{safe_body}"
        if broadcast_type == BroadcastTypeEnum.CRITICAL.value:
            group_text = (
                f"🚨 <b>ЭКСТРЕННОЕ ОПОВЕЩЕНИЕ ДЛЯ ГРУППЫ 240326</b> 🚨\n\n"
                f"<b>{safe_title}</b>\n\n{safe_body}\n\n@all"
            )

        try:
            if settings.GROUP_CHAT_ID:
                await self.bot.send_message(chat_id=settings.GROUP_CHAT_ID, text=group_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"[BROADCASTER] Failed to send message to group chat: {e}")

        # 2. If CRITICAL -> send personal DMs to all active students
        sent_count = 0
        if broadcast_type == BroadcastTypeEnum.CRITICAL.value:
            res = await session.execute(
                select(Student).where(
                    Student.status == StudentStatusEnum.ACTIVE.value, Student.telegram_id.is_not(None)
                )
            )
            students = res.scalars().all()
            bcast.total_recipients = len(students)

            for student in students:
                if not student.telegram_id:
                    continue
                try:
                    dm_text = f"🚨 <b>ВАЖНОЕ ОПОВЕЩЕНИЕ ОТ СТАРОСТЫ</b>\n\n<b>{safe_title}</b>\n\n{safe_body}"
                    await self.bot.send_message(chat_id=student.telegram_id, text=dm_text, parse_mode="HTML")
                    sent_count += 1
                    await asyncio.sleep(self.rate_limit_delay)
                except Exception as e:
                    logger.warning(
                        f"[BROADCASTER] Failed to DM student {student.full_name} ({student.telegram_id}): {e}"
                    )

        bcast.read_count = sent_count
        await session.commit()
        return bcast.id, sent_count


broadcaster_service = BroadcasterService()
