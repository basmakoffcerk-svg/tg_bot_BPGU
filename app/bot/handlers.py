"""
Обработчики команд и сообщений Telegram-бота на aiogram 3.x.
"""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import (
    get_main_menu_keyboard,
    get_starosta_approval_keyboard,
    get_student_claim_keyboard,
)
from app.core.config import settings
from app.core.database import async_session_factory
from app.models import Student

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Точка входа /start: проверяет регистрацию или предлагает выбрать ФИО из вайтлиста."""
    user_tg_id = message.from_user.id
    async with async_session_factory() as db:
        stmt = select(Student).where(Student.telegram_id == user_tg_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()

        if student:
            if student.status == "ACTIVE":
                await message.answer(
                    f"👋 С возвращением, <b>{student.full_name}</b>!\n"
                    f"Группа: <code>240326 Матинф</code> | Подгруппа: <code>{student.subgroup}</code>\n"
                    f"Роль: <b>{student.role}</b>\n\n"
                    f"Нажмите кнопку ниже, чтобы открыть Пульт группы или отметиться на паре:",
                    reply_markup=get_main_menu_keyboard(student.role),
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    f"⏳ Ваша заявка на привязку профиля (<b>{student.full_name}</b>) находится на рассмотрении у старосты.",
                    parse_mode="HTML",
                )
            return

        # Если не привязан — показываем свободный вайтлист
        stmt_free = select(Student).where(Student.telegram_id.is_(None)).order_by(Student.full_name)
        res_free = await db.execute(stmt_free)
        free_students = [(s.id, s.full_name, s.subgroup) for s in res_free.scalars().all()]

        if not free_students:
            await message.answer(
                "❌ Все студенты группы 240326 уже привязаны. Если возникла ошибка, обратитесь к старосте."
            )
            return

        await message.answer(
            "🎓 <b>Добро пожаловать в АРМ Старосты группы 240326 Матинф БГПУ!</b>\n\n"
            "Для начала работы выберите свои ФИО из списка журнала группы:",
            reply_markup=get_student_claim_keyboard(free_students),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("claim_"))
async def process_student_claim(callback: CallbackQuery):
    """Студент выбрал свою фамилию — отправка запроса старосте."""
    student_id = int(callback.data.split("_")[1])
    user_tg_id = callback.from_user.id
    username = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name

    async with async_session_factory() as db:
        stmt = select(Student).where(Student.id == student_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()

        if not student or student.telegram_id is not None:
            await callback.answer("Этот профиль уже занят или не существует.", show_alert=True)
            return

        # Запоминаем ID и ставим статус ожидания
        student.telegram_id = user_tg_id
        student.status = "PENDING"
        await db.commit()

        await callback.message.edit_text(
            f"✅ Запрос на подтверждение отправлен старосте.\n"
            f"Вы выбрали: <b>{student.full_name}</b> (подгруппа {student.subgroup}).\n"
            f"Ожидайте уведомления после подтверждения!",
            parse_mode="HTML",
        )

        # Отправляем уведомление старосте
        if callback.bot and settings.STAROSTA_TELEGRAM_ID:
            try:
                await callback.bot.send_message(
                    chat_id=settings.STAROSTA_TELEGRAM_ID,
                    text=(
                        f"🔔 <b>Запрос на регистрацию в группе 240326:</b>\n\n"
                        f"Пользователь: {username} (ID: <code>{user_tg_id}</code>)\n"
                        f"Заявляет, что он: <b>{student.full_name}</b> (п/г {student.subgroup})\n\n"
                        f"Подтвердить привязку?"
                    ),
                    reply_markup=get_starosta_approval_keyboard(student.id, user_tg_id),
                    parse_mode="HTML",
                )
            except Exception:
                pass


@router.callback_query(F.data.startswith("approve_"))
async def process_approve(callback: CallbackQuery):
    """Староста одобряет привязку студента."""
    _, claim_id_str, tg_id_str = callback.data.split("_")
    claim_id = int(claim_id_str)
    tg_id = int(tg_id_str)

    async with async_session_factory() as db:
        stmt = select(Student).where(Student.id == claim_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()

        if not student:
            await callback.answer("Студент не найден.", show_alert=True)
            return

        student.status = "ACTIVE"
        await db.commit()

        await callback.message.edit_text(
            f"✅ Профиль <b>{student.full_name}</b> успешно подтвержден!",
            parse_mode="HTML",
        )

        # Уведомляем студента
        if callback.bot:
            try:
                await callback.bot.send_message(
                    chat_id=tg_id,
                    text=(
                        f"🎉 <b>Староста подтвердил ваш профиль!</b>\n\n"
                        f"Вы успешно авторизованы как <b>{student.full_name}</b>.\n"
                        f"Теперь вам доступен геочекин и пульт управления:"
                    ),
                    reply_markup=get_main_menu_keyboard(student.role),
                    parse_mode="HTML",
                )
            except Exception:
                pass
