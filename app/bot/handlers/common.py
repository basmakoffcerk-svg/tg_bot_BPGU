"""
Общие обработчики команд: /start, /help, отмена FSM, выбор профиля из вайтлиста.
"""
from __future__ import annotations

import logging
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import (
    get_main_menu_keyboard,
    get_reply_main_keyboard,
    get_starosta_approval_keyboard,
    get_student_claim_keyboard,
)
from app.core.config import settings
from app.core.database import async_session_factory
from app.models import Student

logger = logging.getLogger(__name__)
router = Router(name="common")


@router.message(Command("cancel"))
@router.message(F.text.casefold().in_(["отмена", "❌ отмена", "/cancel"]))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена любого активного FSM-сценария через команду или кнопку."""
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=get_reply_main_keyboard("STUDENT"))
    else:
        await message.answer("Нет активных действий для отмены.")


@router.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext):
    """Инлайн-кнопка отмены FSM."""
    await state.clear()
    await callback.answer("Действие отменено")
    if callback.message:
        await callback.message.edit_text("❌ Действие отменено.")


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """Заглушка для информационных кнопок пагинации."""
    await callback.answer()


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
                role_label = {
                    "STAROSTA": "Староста",
                    "ZAM": "Заместитель старосты",
                    "STUDENT": "Студент",
                }.get(student.role, student.role)

                await message.answer(
                    f"👋 С возвращением, <b>{student.full_name}</b>!\n\n"
                    f"🎓 Группа: <code>240326 Матинф</code> | Подгруппа: <code>{student.subgroup}</code>\n"
                    f"🎖 Роль: <b>{role_label}</b>\n\n"
                    f"Воспользуйтесь меню ниже для просмотра расписания, отметки на паре или выгрузки отчетов:",
                    reply_markup=get_reply_main_keyboard(student.role),
                    parse_mode="HTML",
                )
                await message.answer(
                    "📱 Главное меню Пульта управления:",
                    reply_markup=get_main_menu_keyboard(student.role),
                )
            else:
                await message.answer(
                    f"⏳ Ваша заявка на привязку профиля (<b>{student.full_name}</b>) находится на рассмотрении у старосты.",
                    parse_mode="HTML",
                )
        # Если это староста из .env, но запись еще не создана
        if user_tg_id == settings.STAROSTA_TELEGRAM_ID:
            student = Student(
                full_name=message.from_user.full_name or "Староста",
                subgroup=1,
                role=ROLE_STAROSTA,
                status="ACTIVE",
                telegram_id=user_tg_id,
            )
            db.add(student)
            await db.commit()
            await message.answer(
                f"👋 Добро пожаловать, <b>{student.full_name}</b>!\n\n"
                f"Вы авторизованы как <b>Староста</b>.\n"
                f"Используйте команду /admin для загрузки состава группы и расписания!",
                reply_markup=get_reply_main_keyboard(ROLE_STAROSTA),
                parse_mode="HTML",
            )
            await message.answer(
                "📱 Главное меню Пульта управления:",
                reply_markup=get_main_menu_keyboard(ROLE_STAROSTA),
            )
            return

        # Если не привязан — показываем свободный вайтлист
        stmt_free = select(Student).where(Student.telegram_id.is_(None)).order_by(Student.full_name)
        res_free = await db.execute(stmt_free)
        free_students = [(s.id, s.full_name, s.subgroup) for s in res_free.scalars().all()]

        if not free_students:
            await message.answer(
                "ℹ️ <b>Список группы еще не загружен старостой.</b>\n\n"
                "Староста может загрузить список группы в команду /admin через Excel, CSV или текст.",
                parse_mode="HTML",
            )
            return

        await message.answer(
            "🎓 <b>Добро пожаловать в АРМ Старосты!</b>\n\n"
            "Для начала работы выберите свои ФИО из списка журнала группы:",
            reply_markup=get_student_claim_keyboard(free_students),
            parse_mode="HTML",
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по доступным командам бота."""
    user_tg_id = message.from_user.id
    async with async_session_factory() as db:
        stmt = select(Student).where(Student.telegram_id == user_tg_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()

    role = student.role if student and student.status == "ACTIVE" else "STUDENT"

    text = (
        "📖 <b>Справка по командам АРМ Старосты</b>\n\n"
        "<b>Для всех студентов:</b>\n"
        "▫️ /start — Главное меню и проверка профиля\n"
        "▫️ /schedule — Расписание занятий на сегодня / завтра / неделю\n"
        "▫️ /stats — Персональная статистика посещаемости\n"
        "▫️ 📍 <b>Кнопка «Отметиться на паре (GPS)»</b> — Быстрый геочекин прямо из чата без открытия Mini App\n"
        "▫️ /cancel — Отмена текущего действия\n"
    )
    if role in ("STAROSTA", "ZAM"):
        text += (
            "\n<b>Для старосты и заместителя:</b>\n"
            "▫️ /admin — Панель управления группой\n"
            "▫️ 👥 Управление группой — просмотр, добавление, экспорт списка\n"
            "▫️ 📊 Экспресс-шахматка — онлайн-журнал текущей пары с быстрой сменой статусов\n"
            "▫️ 📑 Запросить Excel — генерация официальной рапортички БГПУ\n"
            "▫️ 📢 Оповещение — рассылка срочных и информационных сообщений\n"
        )

    await message.answer(text, parse_mode="HTML")


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

        student.telegram_id = user_tg_id
        student.status = "PENDING"
        await db.commit()

        if callback.message:
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
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление старосте: {e}")


@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    """Возврат в главное меню."""
    user_tg_id = callback.from_user.id
    async with async_session_factory() as db:
        stmt = select(Student).where(Student.telegram_id == user_tg_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()

    role = student.role if student else "STUDENT"
    if callback.message:
        await callback.message.edit_text(
            "📱 <b>Главное меню Пульта управления:</b>",
            reply_markup=get_main_menu_keyboard(role),
            parse_mode="HTML",
        )
    await callback.answer()
