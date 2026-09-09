import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.keyboards import (
    get_main_menu_keyboard,
    get_starosta_approval_keyboard,
    get_students_whitelist_keyboard,
)
from core.config import settings
from core.database import AsyncSessionLocal
from models import RoleEnum, Student, StudentStatusEnum

logger = logging.getLogger("onboarding")
router = Router()


@router.message(CommandStart())
async def handle_start_command(message: Message):
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        # Check if user already exists and registered
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()

        if student:
            if student.status == StudentStatusEnum.ACTIVE.value:
                role_label = {
                    RoleEnum.STAROSTA.value: "👑 Староста",
                    RoleEnum.ZAM.value: "⭐ Заместитель старосты",
                    RoleEnum.STUDENT.value: "🎓 Студент",
                }.get(student.role, "Студент")

                welcome_text = (
                    f"👋 С возвращением, <b>{student.full_name}</b>!\n"
                    f"Роль: {role_label} | Подгруппа: {student.subgroup}\n"
                    f"Академическая группа: <b>240326 «Матинф» БГПУ</b>\n\n"
                    "Нажмите кнопку <b>«📱 Открыть Пульт (Mini App)»</b> ниже, "
                    "чтобы отметиться на текущей паре или посмотреть расписание."
                )
                is_starosta = student.role in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value)
                await message.answer(
                    text=welcome_text,
                    reply_markup=get_main_menu_keyboard(is_starosta=is_starosta),
                    parse_mode="HTML"
                )
                return
            elif student.status == StudentStatusEnum.PENDING.value:
                await message.answer(
                    text=(
                        f"⏳ <b>{student.full_name}</b>, ваша заявка на привязку аккаунта "
                        "находится на рассмотрении у старосты.\n"
                        "Как только староста подтвердит профиль, вам придет уведомление."
                    ),
                    parse_mode="HTML",
                )
                return
            elif student.status == StudentStatusEnum.BLOCKED.value:
                await message.answer("⛔ Ваш аккаунт заблокирован. Обратитесь к старосте группы.")
                return

        # User is not linked -> Show whitelist of unlinked students
        unlinked_res = await session.execute(
            select(Student).where(Student.telegram_id.is_(None)).order_by(Student.full_name)
        )
        unlinked_students = unlinked_res.scalars().all()

        if not unlinked_students:
            await message.answer("⚠️ В вайтлисте группы 240326 нет свободных профилей. Обратитесь к старосте.")
            return

        kb = get_students_whitelist_keyboard(unlinked_students, page=0)
        intro_text = (
            f"👋 Здравствуйте, <b>{message.from_user.full_name}</b>!\n\n"
            f"Добро пожаловать в систему <b>«АРМ Старосты»</b> группы <b>240326 «Матинф»</b> БГПУ.\n"
            f"Для начала работы выберите свои <b>Фамилию Имя Отчество</b> из официального списка группы:"
        )
        await message.answer(text=intro_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("whitelist_page:"))
async def handle_whitelist_pagination(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 2 or not parts[1].isdigit():
        await callback.answer()
        return
    page = int(parts[1])

    async with AsyncSessionLocal() as session:
        unlinked_res = await session.execute(
            select(Student).where(Student.telegram_id.is_(None)).order_by(Student.full_name)
        )
        unlinked_students = unlinked_res.scalars().all()

        if not unlinked_students:
            await callback.answer("Все профили уже привязаны!", show_alert=True)
            return

        kb = get_students_whitelist_keyboard(unlinked_students, page=page)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()


@router.callback_query(F.data.startswith("claim_student:"))
async def handle_student_claim(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) < 2 or not parts[1].isdigit():
        await callback.answer("Некорректные данные запроса!", show_alert=True)
        return
    student_id = int(parts[1])
    user_id = callback.from_user.id
    user_handle = callback.from_user.username
    user_tag = f"@{user_handle}" if user_handle else callback.from_user.full_name

    async with AsyncSessionLocal() as session:
        # Check if telegram_id is already assigned elsewhere
        existing_res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        existing = existing_res.scalar_one_or_none()
        if existing:
            await callback.answer("Вы уже привязаны к профилю группы!", show_alert=True)
            return

        # Fetch requested student
        res = await session.execute(select(Student).where(Student.id == student_id))
        student = res.scalar_one_or_none()
        if not student:
            await callback.answer("Студент не найден!", show_alert=True)
            return

        if student.telegram_id is not None:
            await callback.answer("Этот профиль уже занят другим пользователем!", show_alert=True)
            return

        # Set user as PENDING
        student.telegram_id = user_id
        student.status = StudentStatusEnum.PENDING.value
        await session.commit()

        # Notify student
        safe_student_name = html.escape(student.full_name)
        await callback.message.edit_text(
            f"✅ Вы выбрали: <b>{safe_student_name}</b> ({student.subgroup} подгруппа).\n\n"
            "Запрос отправлен старосте на подтверждение. Ожидайте уведомления...",
            parse_mode="HTML",
        )
        await callback.answer("Запрос отправлен старосте!")

        # Send approval request to Starosta
        if settings.STAROSTA_TELEGRAM_ID:
            safe_user_tag = html.escape(user_tag)
            approval_text = (
                f"🔔 <b>Запрос на привязку профиля</b>\n\n"
                f"Пользователь: {safe_user_tag} (ID: <code>{user_id}</code>)\n"
                f"Заявляет, что он: <b>{safe_student_name}</b>\n"
                f"Подгруппа: <b>{student.subgroup}</b>\n\n"
                "Подтвердить личность студента?"
            )
            try:
                await bot.send_message(
                    chat_id=settings.STAROSTA_TELEGRAM_ID,
                    text=approval_text,
                    reply_markup=get_starosta_approval_keyboard(student.id, user_id),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify Starosta: {e}")


@router.callback_query(F.data.startswith("approve_claim:"))
async def handle_approve_claim(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await callback.answer("Некорректные данные запроса!", show_alert=True)
        return
    student_id = int(parts[1])
    target_tg_id = int(parts[2])

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.id == student_id))
        student = res.scalar_one_or_none()
        if not student:
            await callback.answer("Студент не найден", show_alert=True)
            return

        student.status = StudentStatusEnum.ACTIVE.value
        student.telegram_id = target_tg_id
        await session.commit()

        await callback.message.edit_text(
            f"✅ <b>Заявка подтверждена!</b>\nСтудент: <b>{student.full_name}</b> активирован в группе 240326.",
            parse_mode="HTML",
        )
        await callback.answer("Студент подтвержден!")

        # Notify student with full menu
        try:
            congrats_text = (
                f"🎉 Поздравляем, <b>{student.full_name}</b>!\n\n"
                f"Староста подтвердил ваш профиль в группе <b>240326 «Матинф»</b>.\n"
                f"Теперь вам доступен весь функционал геочекина и расписания через <b>Telegram Mini App</b>."
            )
            await bot.send_message(
                chat_id=target_tg_id, text=congrats_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to send activation notice to student: {e}")


@router.callback_query(F.data.startswith("reject_claim:"))
async def handle_reject_claim(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await callback.answer("Некорректные данные запроса!", show_alert=True)
        return
    student_id = int(parts[1])
    target_tg_id = int(parts[2])

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.id == student_id))
        student = res.scalar_one_or_none()
        if student:
            student.telegram_id = None
            student.status = StudentStatusEnum.PENDING.value
            await session.commit()

        await callback.message.edit_text(
            f"❌ Заявка на студента <b>{student.full_name if student else 'Студент'}</b> отклонена.", parse_mode="HTML"
        )
        await callback.answer("Заявка отклонена")

        try:
            await bot.send_message(
                chat_id=target_tg_id,
                text=(
                    "❌ Ваша заявка на привязку профиля была отклонена старостой. "
                    "Выберите свои реальные ФИО через /start."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
